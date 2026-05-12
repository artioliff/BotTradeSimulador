from .base import EstrategiaBase
from collections import deque


class ADXStrategy(EstrategiaBase):
    def __init__(self, symbol: str, periodo: int = 14,
                 limiar_tendencia: int = 25,
                 quantidade_por_trade: float = 0.001,
                 percentual_por_trade: float | None = None,
                 saldo_inicial: float = 10000,
                 stop_loss_percent: float = 0.02,
                 take_profit_percent: float = 0.03,
                 trailing_stop_percent: float = 0.01,
                 usar_filtro_volume: bool = False,
                 usar_saida_gradual: bool = False):
        super().__init__(symbol, saldo_inicial)
        self.periodo = periodo
        self.limiar_tendencia = limiar_tendencia
        self.quantidade_por_trade = quantidade_por_trade
        self.percentual_por_trade = percentual_por_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.usar_filtro_volume = usar_filtro_volume
        self.usar_saida_gradual = usar_saida_gradual

        self.historico_highs = deque(maxlen=1000)
        self.historico_lows = deque(maxlen=1000)
        self.historico_volumes = deque(maxlen=1000)
        self.historico_dx = deque(maxlen=100)

        self.em_posicao: bool = False
        self.preco_compra_medio: float = 0
        self.quantidade_comprada_total: float = 0
        self.maior_preco_posicao: float = 0
        self.adx_atual: float = 0
        self.di_plus_atual: float = 0
        self.di_minus_atual: float = 0

    @staticmethod
    def calcular_true_range(high: float, low: float, prev_close: float) -> float:
        hl = high - low
        hc = abs(high - prev_close)
        lc = abs(low - prev_close)
        return max(hl, hc, lc)

    @staticmethod
    def calcular_dm(high: float, low: float,
                    prev_high: float, prev_low: float) -> tuple[float, float]:
        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = up_move if up_move > down_move and up_move > 0 else 0
        minus_dm = down_move if down_move > up_move and down_move > 0 else 0

        return plus_dm, minus_dm

    def calcular_adx(self, highs, lows, closes):
        if len(closes) < self.periodo * 2:
            return None, None, None

        highs_list = list(highs)
        lows_list = list(lows)
        closes_list = list(closes)

        n = len(closes_list)

        tr_list = [0]
        plus_dm_list = [0]
        minus_dm_list = [0]

        for i in range(1, n):
            tr = self.calcular_true_range(highs_list[i], lows_list[i], closes_list[i-1])
            tr_list.append(tr)

            plus_dm, minus_dm = self.calcular_dm(highs_list[i], lows_list[i],
                                                  highs_list[i-1], lows_list[i-1])
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)

        tr_smooth = sum(tr_list[1:self.periodo+1]) / self.periodo
        plus_dm_smooth = sum(plus_dm_list[1:self.periodo+1]) / self.periodo
        minus_dm_smooth = sum(minus_dm_list[1:self.periodo+1]) / self.periodo

        for i in range(self.periodo + 1, n):
            tr_smooth = (tr_smooth * (self.periodo - 1) + tr_list[i]) / self.periodo
            plus_dm_smooth = (plus_dm_smooth * (self.periodo - 1) + plus_dm_list[i]) / self.periodo
            minus_dm_smooth = (minus_dm_smooth * (self.periodo - 1) + minus_dm_list[i]) / self.periodo

        plus_di = 100 * (plus_dm_smooth / tr_smooth) if tr_smooth > 0 else 0
        minus_di = 100 * (minus_dm_smooth / tr_smooth) if tr_smooth > 0 else 0

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0

        return dx, plus_di, minus_di

    def _calcular_adx_suavizado(self, dx: float) -> float:
        self.historico_dx.append(dx)

        if len(self.historico_dx) < self.periodo:
            return 0

        if len(self.historico_dx) == self.periodo:
            return sum(self.historico_dx) / self.periodo

        adx_anterior = self.adx_atual or sum(self.historico_dx[:-1]) / (len(self.historico_dx) - 1)
        return (adx_anterior * (self.periodo - 1) + dx) / self.periodo

    def _checar_filtro_volume(self, volume_atual: float) -> bool:
        if not self.usar_filtro_volume or len(self.historico_volumes) < 20:
            return True

        volumes_list = list(self.historico_volumes)
        volume_medio = sum(volumes_list[-20:]) / 20

        return volume_atual >= volume_medio * 0.8

    def processar_preco(self, preco: float, timestamp, high: float | None = None,
                        low: float | None = None, volume: float | None = None, **kwargs):
        self.ultimo_preco = preco
        self.historico_precos.append(preco)

        if high is None or low is None:
            volatilidade = preco * 0.002
            high = preco + volatilidade
            low = preco - volatilidade

        self.historico_highs.append(high)
        self.historico_lows.append(low)

        if volume is not None:
            self.historico_volumes.append(volume)

        if len(self.historico_precos) < self.periodo * 2:
            return []

        dx, plus_di, minus_di = self.calcular_adx(
            self.historico_highs, self.historico_lows, self.historico_precos)

        if dx is None:
            return []

        adx = self._calcular_adx_suavizado(dx)
        self.adx_atual = adx
        self.di_plus_atual = plus_di
        self.di_minus_atual = minus_di

        if len(self.historico_precos) % 20 == 0:
            print(f"  ADX: {adx:.1f} | +DI: {plus_di:.1f} | -DI: {minus_di:.1f} | Tendência: {'ALTA' if plus_di > minus_di else 'BAIXA'}")

        ordens_executadas = []

        trade = self._verificar_stop_take_trailing(
            preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
            self.trailing_stop_percent, adx=adx, plus_di=plus_di, minus_di=minus_di)
        if trade:
            print(f"  >>> {trade['motivo']} ACIONADO!")
            ordens_executadas.append(trade)
            return ordens_executadas

        if adx >= self.limiar_tendencia and plus_di > minus_di and not self.em_posicao:
            if volume is not None and self.usar_filtro_volume:
                if not self._checar_filtro_volume(volume):
                    print(f"  [FILTRO] Volume insuficiente, ignorando compra")
                    return ordens_executadas

            if self.percentual_por_trade:
                valor_investir = self.saldo_usdt * self.percentual_por_trade
                quantidade = round(valor_investir / preco, 8)
                print(f"  Investindo {self.percentual_por_trade*100}% do saldo (${self.saldo_usdt:.2f})")
            else:
                quantidade = self.quantidade_por_trade
                valor_necessario = quantidade * preco
                if valor_necessario > self.saldo_usdt:
                    print(f"  [ERRO] Saldo insuficiente! Necessário ${valor_necessario:.2f}")
                    return ordens_executadas

            trade = self.executar_compra(preco, quantidade, timestamp,
                                        sinal='COMPRA_ADX',
                                        adx=round(adx, 1),
                                        plus_di=round(plus_di, 1),
                                        minus_di=round(minus_di, 1))
            if trade:
                self.em_posicao = True
                self.preco_compra_medio = preco
                self.quantidade_comprada_total = quantidade
                self.maior_preco_posicao = preco
                ordens_executadas.append(trade)

        elif adx >= self.limiar_tendencia and minus_di > plus_di and self.em_posicao:
            quantidade_vender = self.quantidade_comprada_total

            if self.usar_saida_gradual and self.preco_compra_medio > 0:
                ganho_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio
                if ganho_percentual >= 0.06:
                    quantidade_vender = self.quantidade_comprada_total
                elif ganho_percentual >= 0.04:
                    quantidade_vender = self.quantidade_comprada_total * 0.5
                elif ganho_percentual >= 0.02:
                    quantidade_vender = self.quantidade_comprada_total * 0.25
                else:
                    quantidade_vender = self.quantidade_comprada_total

            trade = self.executar_venda(preco, quantidade_vender, timestamp,
                                        sinal='VENDA_ADX',
                                        adx=round(adx, 1),
                                        plus_di=round(plus_di, 1),
                                        minus_di=round(minus_di, 1))
            if trade:
                self.quantidade_comprada_total -= quantidade_vender
                if self.quantidade_comprada_total <= 0:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    self.preco_compra_medio = 0
                    self.maior_preco_posicao = 0
                ordens_executadas.append(trade)

        return ordens_executadas

    def reset(self):
        super().reset()
        self.historico_highs = deque(maxlen=1000)
        self.historico_lows = deque(maxlen=1000)
        self.historico_volumes = deque(maxlen=1000)
        self.historico_dx = deque(maxlen=100)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.adx_atual = 0
        self.di_plus_atual = 0
        self.di_minus_atual = 0

    def get_configuracao(self):
        if self.percentual_por_trade:
            gestao_quantidade = f"{self.percentual_por_trade*100}% do saldo"
        else:
            simbolo_asset = self.symbol.replace('USDT', '')
            gestao_quantidade = f"{self.quantidade_por_trade} {simbolo_asset} (fixo)"

        return {
            'nome': 'ADX - Average Directional Index',
            'descricao': 'Compra quando ADX > limiar e +DI > -DI. Vende quando ADX > limiar e -DI > +DI. ADX suavizado corretamente (Wilder smoothing duplo).',
            'parametros': {
                'periodo_adx': self.periodo,
                'limiar_tendencia': self.limiar_tendencia,
                'gestao_de_quantidade': gestao_quantidade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%",
                'filtro_volume': self.usar_filtro_volume,
                'saida_gradual': self.usar_saida_gradual
            }
        }
