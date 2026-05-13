from .base import EstrategiaBase
from collections import deque


class RSIStrategy(EstrategiaBase):
    def __init__(self, symbol: str, periodo: int = 14,
                 limite_inferior: int = 30, limite_superior: int = 70,
                 quantidade_por_trade: float = 0.001,
                 percentual_por_trade: float | None = None,
                 saldo_inicial: float = 10000,
                 usar_saida_gradual: bool = False,
                 stop_loss_percent: float = 0.02,
                 take_profit_percent: float = 0.03,
                 trailing_stop_percent: float = 0.01,
                 max_perdas_consecutivas: int = 5,
                 cooldown_periods: int = 10,
                 usar_filtro_tendencia: bool = False,
                 usar_filtro_volume: bool = False,
                 debug: bool = False):
        super().__init__(symbol, saldo_inicial, debug=debug)
        self.periodo = periodo
        self.limite_inferior = limite_inferior
        self.limite_superior = limite_superior
        self.quantidade_por_trade = quantidade_por_trade
        self.percentual_por_trade = percentual_por_trade
        self.usar_saida_gradual = usar_saida_gradual
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.max_perdas_consecutivas = max_perdas_consecutivas
        self.usar_filtro_tendencia = usar_filtro_tendencia
        self.usar_filtro_volume = usar_filtro_volume

        self.cooldown_periods_counter: int = 0
        self.cooldown_max_periods: int = cooldown_periods
        self.historico_volumes = deque(maxlen=1000)
        self.historico_rsi = deque(maxlen=1000)
        self.em_posicao: bool = False
        self.preco_compra_medio: float = 0
        self.quantidade_comprada_total: float = 0
        self.maior_preco_posicao: float = 0
        self.perdas_consecutivas: int = 0
        self.volume_atual: float = 0
        self.ultima_venda_percentual: float = 0

    def _checar_filtros(self, preco: float, rsi: float) -> bool:
        if len(self.historico_precos) >= 200:
            precos_lista = list(self.historico_precos)
            media_200 = sum(precos_lista[-200:]) / 200

            if preco > media_200 * 1.05:
                if len(self.historico_rsi) % 20 == 0:
                    print(f"  [FILTRO] Preço {preco:.2f} muito acima da média 200 ({media_200:.2f}), ignorando compra")
                return False

            if preco < media_200 * 0.85:
                if len(self.historico_rsi) % 20 == 0:
                    print(f"  [FILTRO] Mercado extremamente baixista ({preco:.2f} < 85% da média), risco alto")
                return False

        if self.usar_filtro_tendencia and len(self.historico_precos) >= 50:
            ema_9 = self.calcular_media_movel_exponencial(self.historico_precos, 9)
            ema_21 = self.calcular_media_movel_exponencial(self.historico_precos, 21)

            if ema_9 is not None and ema_21 is not None:
                if ema_9 < ema_21 and rsi <= self.limite_inferior:
                    if len(self.historico_rsi) % 20 == 0:
                        print(f"  [FILTRO] Tendência de baixa (EMA9 < EMA21), ignorando compra")
                    return False

        if self.usar_filtro_volume and len(self.historico_volumes) >= 20:
            if self.volume_atual > 0:
                volumes_lista = list(self.historico_volumes)
                volume_medio = sum(volumes_lista[-20:]) / 20
                if self.volume_atual < volume_medio * 0.7:
                    if len(self.historico_rsi) % 20 == 0:
                        print(f"  [FILTRO] Volume baixo ({self.volume_atual:.0f} < {volume_medio*0.7:.0f})")
                    return False

        return True

    def processar_preco(self, preco: float, timestamp, volume: float | None = None, **kwargs):
        self.ultimo_preco = preco
        self.historico_precos.append(preco)

        if volume is not None:
            self.volume_atual = volume
            self.historico_volumes.append(volume)

        if self.cooldown_periods_counter > 0:
            self.cooldown_periods_counter -= 1
            if self.cooldown_periods_counter == 0:
                print(f"  >>> COOLDOWN ENCERRADO - Retomando operacoes")
            return []

        if len(self.historico_precos) < self.periodo + 1:
            return []

        rsi = self.calcular_rsi_wilder(self.historico_precos, self.periodo)
        self.historico_rsi.append({'timestamp': timestamp, 'rsi': rsi, 'preco': preco})

        if len(self.historico_rsi) % 10 == 0:
            print(f"  RSI: {rsi:.1f} | Sobrecompra: {rsi >= self.limite_superior} | Sobrevenda: {rsi <= self.limite_inferior}")

        ordens_executadas = []

        trade = self._verificar_stop_take_trailing(
            preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
            self.trailing_stop_percent, rsi=rsi)
        if trade:
            print(f"  >>> {trade['motivo']} ACIONADO!")
            if trade['motivo'] == 'STOP_LOSS':
                self.perdas_consecutivas += 1
                print(f"      Perdas consecutivas: {self.perdas_consecutivas}/{self.max_perdas_consecutivas}")
                if self.perdas_consecutivas >= self.max_perdas_consecutivas:
                    self.cooldown_periods_counter = self.cooldown_max_periods
                    print(f"  >>> COOLDOWN ATIVADO por {self.cooldown_max_periods} candles")
                    self.perdas_consecutivas = 0
            else:
                self.perdas_consecutivas = 0
            ordens_executadas.append(trade)
            return ordens_executadas

        if rsi <= self.limite_inferior and not self.em_posicao:
            if not self._checar_filtros(preco, rsi):
                return ordens_executadas

            if self.percentual_por_trade:
                valor_investir = self.saldo_usdt * self.percentual_por_trade
                quantidade = round(valor_investir / preco, 8)
                print(f"  Investindo {self.percentual_por_trade*100}% do saldo (${self.saldo_usdt:.2f}) = ${valor_investir:.2f} -> {quantidade:.8f} {self.symbol.replace('USDT', '')}")
            else:
                quantidade = self.quantidade_por_trade
                valor_necessario = quantidade * preco

                if valor_necessario > self.saldo_usdt:
                    print(f"  [ERRO] Saldo insuficiente! Necessário ${valor_necessario:.2f}, tem ${self.saldo_usdt:.2f}")
                    return ordens_executadas

            trade = self.executar_compra(preco, quantidade, timestamp,
                                        rsi=rsi, sinal='SOBREVENDA')
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = quantidade
                self.maior_preco_posicao = preco
                ordens_executadas.append(trade)

        elif rsi >= self.limite_superior and self.em_posicao:
            quantidade_vender = self.quantidade_comprada_total

            if self.usar_saida_gradual and self.preco_compra_medio > 0:
                ganho_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio

                if ganho_percentual >= 0.06:
                    quantidade_vender = self.quantidade_comprada_total
                    print(f"  Saída gradual: ALVO 3 - {ganho_percentual*100:.1f}% lucro, vendendo tudo")
                elif ganho_percentual >= 0.04:
                    quantidade_vender = self.quantidade_comprada_total * 0.5
                    print(f"  Saída gradual: ALVO 2 - {ganho_percentual*100:.1f}% lucro, vendendo 50%")
                elif ganho_percentual >= 0.02:
                    quantidade_vender = self.quantidade_comprada_total * 0.25
                    print(f"  Saída gradual: ALVO 1 - {ganho_percentual*100:.1f}% lucro, vendendo 25%")
                else:
                    quantidade_vender = 0
                    print(f"  Saída gradual: Esperando mais ({ganho_percentual*100:.1f}% < 2%)")

            if quantidade_vender > 0:
                trade = self.executar_venda(preco, quantidade_vender, timestamp,
                                           rsi=rsi, sinal='SOBRECOMPRA')
                if trade:
                    self.quantidade_comprada_total -= quantidade_vender
                    if self.quantidade_comprada_total <= 0.00000001:
                        self.em_posicao = False
                        self.quantidade_comprada_total = 0
                        self.preco_compra_medio = 0
                        self.maior_preco_posicao = 0
                        self.perdas_consecutivas = 0
                    ordens_executadas.append(trade)

        return ordens_executadas

    def reset(self):
        super().reset()
        self.historico_volumes = deque(maxlen=1000)
        self.historico_rsi = deque(maxlen=1000)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.cooldown_periods_counter = 0
        self.volume_atual = 0
        self.ultima_venda_percentual = 0

    def get_configuracao(self):
        if self.percentual_por_trade:
            gestao_quantidade = f"{self.percentual_por_trade*100}% do saldo"
        else:
            simbolo_asset = self.symbol.replace('USDT', '')
            gestao_quantidade = f"{self.quantidade_por_trade} {simbolo_asset} (fixo)"

        return {
            'nome': 'RSI - Relative Strength Index (Versão Melhorada)',
            'descricao': 'Compra em sobrevenda (RSI < limite_inferior) e vende em sobrecompra (RSI > limite_superior) com protecoes de STOP-LOSS, TAKE-PROFIT e TRAILING STOP. Inclui filtros de tendencia e volume, cooldown apos perdas consecutivas, e saida gradual corrigida.',
            'parametros': {
                'periodo_rsi': self.periodo,
                'limite_inferior_sobrevenda': self.limite_inferior,
                'limite_superior_sobrecompra': self.limite_superior,
                'gestao_de_quantidade': gestao_quantidade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'saida_gradual': self.usar_saida_gradual,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%",
                'max_perdas_consecutivas': self.max_perdas_consecutivas,
                'cooldown_apos_perdas': self.cooldown_max_periods,
                'filtro_tendencia_ema': self.usar_filtro_tendencia,
                'filtro_volume': self.usar_filtro_volume
            }
        }
