# estrategias/bollinger_bands.py
from .base import EstrategiaBase
from collections import deque
from datetime import datetime

class BollingerBandsStrategy(EstrategiaBase):
    """
    Estrategia baseada em Bandas de Bollinger (Versão Melhorada).
    
    Sinais:
    - Compra quando preço toca/cruza banda inferior COM confirmação
    - Vende quando preço toca/cruza banda superior OU reversão no meio
    
    Melhorias:
    - Stop-loss, take-profit, trailing stop
    - Filtro de tendência (não comprar em tendência de baixa)
    - Filtro de largura de banda (evitar falsos sinais)
    - Confirmação de candle (evitar whipsaw)
    - Saída gradual em tendências fortes
    - Cooldown após perdas consecutivas
    """
    
    def __init__(self, symbol, periodo=20, desvios=2,
                 quantidade_por_trade=0.001, percentual_por_trade=None, saldo_inicial=10000,
                 usar_filtro_tendencia=True, usar_confirmacao_candle=True,
                 banda_min_largura=0.02, banda_max_largura=0.10,
                 stop_loss_percent=0.02, take_profit_percent=0.03,
                 trailing_stop_percent=0.01, usar_saida_gradual=False,
                 vender_na_media=False, percentual_venda_media=0.5,
                 max_perdas_consecutivas=3, cooldown_periods=10,
                 debug=False):
        """
        Args:
            symbol: Simbolo do ativo
            periodo: Periodo para calcular as bandas (padrao: 20)
            desvios: Numero de desvios padrao (padrao: 2)
            quantidade_por_trade: Quantidade fixa por operacao
            percentual_por_trade: Percentual do saldo a usar
            saldo_inicial: Saldo inicial em USDT
            usar_filtro_tendencia: Se True, so opera na direcao da tendencia
            usar_confirmacao_candle: Se True, espera candle fechar para confirmar
            banda_min_largura: Largura minima da banda para considerar (2%)
            banda_max_largura: Largura maxima da banda para considerar (10%)
            stop_loss_percent: Percentual de stop-loss
            take_profit_percent: Percentual de take-profit
            trailing_stop_percent: Percentual de trailing stop
            usar_saida_gradual: Se True, vende em partes
            vender_na_media: Se True, vende parte quando preço atinge média
            percentual_venda_media: Percentual a vender na média (ex: 0.5 = 50%)
            max_perdas_consecutivas: Maximo de perdas seguidas antes de pausar
            cooldown_periods: Quantos candles esperar apos muitas perdas
            debug: Se True, exibe logs detalhados
        """
        super().__init__(symbol, saldo_inicial, debug=debug)
        
        # Parâmetros Bollinger
        self.periodo = periodo
        self.desvios = desvios
        self.quantidade_por_trade = quantidade_por_trade
        self.percentual_por_trade = percentual_por_trade
        
        # Filtros
        self.usar_filtro_tendencia = usar_filtro_tendencia
        self.usar_confirmacao_candle = usar_confirmacao_candle
        self.banda_min_largura = banda_min_largura
        self.banda_max_largura = banda_max_largura
        
        # Proteções
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.usar_saida_gradual = usar_saida_gradual
        self.vender_na_media = vender_na_media
        self.percentual_venda_media = percentual_venda_media
        
        # Cooldown
        self.max_perdas_consecutivas = max_perdas_consecutivas
        self.cooldown_periods_counter = 0
        self.cooldown_max_periods = cooldown_periods
        
        # Estado
        self.historico_bandas = deque(maxlen=1000)
        self.historico_volumes = deque(maxlen=1000)
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.volume_atual = 0
        
        # Confirmação de candle
        self.ultimo_sinal_compra = None
        self.ultimo_sinal_venda = None
        self.candle_aberto_compra = False
        self.candle_aberto_venda = False

        # Cooldown venda na média (evita múltiplas vendas na mesma região)
        self._cooldown_venda_media: int = 0
        self._cooldown_venda_media_max: int = 5
        
        # Estatísticas
        self.sinais_compra = {'BANDA_INFERIOR': 0, 'REVERSAO_MEDIA': 0}
        self.sinais_venda = {'BANDA_SUPERIOR': 0, 'MEDIA': 0}
        self.banda_largura_atual = 0
    
    def _calcular_bandas(self, precos):
        """Calcula banda superior, media e banda inferior"""
        if len(precos) < self.periodo:
            return None, None, None, 0
        
        precos_lista = list(precos)
        preco_atual = precos_lista[-1]
        
        # Usa últimos 'periodo' preços
        ultimos_precos = precos_lista[-self.periodo:]
        media = sum(ultimos_precos) / self.periodo
        
        # Calcula desvio padrão
        variancia = sum((p - media) ** 2 for p in ultimos_precos) / self.periodo
        desvio = variancia ** 0.5
        
        banda_superior = media + (desvio * self.desvios)
        banda_inferior = media - (desvio * self.desvios)
        
        # Calcula largura da banda (volatilidade)
        largura = (banda_superior - banda_inferior) / media
        
        return banda_superior, media, banda_inferior, largura
    
    def _calcular_tendencia(self):
        """Calcula tendência baseada na posição do preço em relação às bandas"""
        if len(self.historico_bandas) < 10:
            return 'NEUTRO', 0
        
        ultimas_bandas = list(self.historico_bandas)[-10:]
        preco_atual = self.historico_precos[-1]
        
        # Calcula percentual de tempo que o preço ficou acima da média
        acima_media = sum(1 for b in ultimas_bandas if b['preco'] > b['media']) / len(ultimas_bandas)
        
        # Calcula posição atual nas bandas (0 = banda inf, 0.5 = media, 1 = banda sup)
        ultima_banda = ultimas_bandas[-1]
        if ultima_banda['banda_superior'] != ultima_banda['banda_inferior']:
            posicao_banda = (preco_atual - ultima_banda['banda_inferior']) / (ultima_banda['banda_superior'] - ultima_banda['banda_inferior'])
        else:
            posicao_banda = 0.5
        
        if acima_media > 0.7 and posicao_banda > 0.6:
            forca = (posicao_banda - 0.5) * 2
            return 'ALTA', forca
        elif acima_media < 0.3 and posicao_banda < 0.4:
            forca = (0.5 - posicao_banda) * 2
            return 'BAIXA', forca
        else:
            return 'LATERAL', 0
    
    def _calcular_quantidade(self, preco: float):
        if self.percentual_por_trade:
            valor_investir = self.saldo_usdt * self.percentual_por_trade
            quantidade = round(valor_investir / preco, 8)
            return quantidade, valor_investir
        else:
            quantidade = self.quantidade_por_trade
            valor_necessario = quantidade * preco
            
            if valor_necessario > self.saldo_usdt:
                self._log(f"Saldo insuficiente! Necessário ${valor_necessario:.2f}, tem ${self.saldo_usdt:.2f}", "ERRO")
                return None, None
            
            return quantidade, valor_necessario
    
    def _verificar_banda_larga_valida(self, largura):
        """Verifica se a largura da banda está dentro dos limites aceitáveis"""
        if largura < self.banda_min_largura:
            self._log(f"Banda muito estreita ({largura*100:.2f}% < {self.banda_min_largura*100:.2f}%), poucos sinais", "FILTRO")
            return False
        if largura > self.banda_max_largura:
            self._log(f"Banda muito larga ({largura*100:.2f}% > {self.banda_max_largura*100:.2f}%), risco alto", "FILTRO")
            return False
        return True
    
    def processar_preco(self, preco, timestamp, volume=None, is_candle_closed=True, **kwargs):
        """
        Processa cada preco com Bandas de Bollinger
        
        Args:
            preco: Preco atual (geralmente fechamento)
            timestamp: Timestamp do candle
            volume: Volume do candle (opcional)
            is_candle_closed: Se True, candle está fechado (confirmação)
        """
        self.ultimo_preco = preco
        self.historico_precos.append(preco)
        
        if volume is not None:
            self.volume_atual = volume
            self.historico_volumes.append(volume)
        
        # ============================================
        # COOLDOWN (perdas consecutivas)
        # ============================================
        if self.cooldown_periods_counter > 0:
            self.cooldown_periods_counter -= 1
            if self.cooldown_periods_counter == 0:
                self._log("COOLDOWN encerrado - Retomando operações", "INFO")
            return []

        if self._cooldown_venda_media > 0:
            self._cooldown_venda_media -= 1
        
        # ============================================
        # DADOS SUFICIENTES?
        # ============================================
        if len(self.historico_precos) < self.periodo:
            return []
        
        # ============================================
        # CALCULA BANDAS
        # ============================================
        banda_sup, media, banda_inf, largura = self._calcular_bandas(self.historico_precos)
        
        if banda_sup is None or media is None or banda_inf is None:
            return []
        
        self.banda_largura_atual = largura
        
        # Armazena histórico
        self.historico_bandas.append({
            'timestamp': timestamp,
            'preco': preco,
            'banda_superior': banda_sup,
            'media': media,
            'banda_inferior': banda_inf,
            'largura': largura
        })
        
        # ============================================
        # FILTRO DE LARGURA DA BANDA
        # ============================================
        banda_valida = self._verificar_banda_larga_valida(largura)
        
        # ============================================
        # CALCULA TENDENCIA
        # ============================================
        tendencia, forca_tendencia = self._calcular_tendencia() if self.usar_filtro_tendencia else ('NEUTRO', 0)
        
        # ============================================
        # LOG PERIODICO
        # ============================================
        if len(self.historico_bandas) % 10 == 0:
            print(f"  BB: Sup={banda_sup:.2f} Med={media:.2f} Inf={banda_inf:.2f} | Largura={largura*100:.2f}% | Tend: {tendencia}")
        
        ordens_executadas = []
        banda_info = {
            'banda_superior': banda_sup,
            'media': media,
            'banda_inferior': banda_inf,
            'largura': largura
        }
        
        # ============================================
        # VERIFICA PROTECÇÕES (Stop, Take, Trailing)
        # ============================================
        if self.em_posicao:
            trade_protecao = self._verificar_stop_take_trailing(
                preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
                self.trailing_stop_percent,
                banda_superior=round(banda_sup, 2), media=round(media, 2),
                banda_inferior=round(banda_inf, 2))
            if trade_protecao:
                if trade_protecao['motivo'] == 'STOP_LOSS':
                    self.perdas_consecutivas += 1
                    self._log(f"Perdas consecutivas: {self.perdas_consecutivas}/{self.max_perdas_consecutivas}")
                    if self.perdas_consecutivas >= self.max_perdas_consecutivas:
                        self.cooldown_periods_counter = self.cooldown_max_periods
                        self._log(f"COOLDOWN ativado por {self.cooldown_max_periods} candles")
                        self.perdas_consecutivas = 0
                else:
                    self.perdas_consecutivas = 0
                ordens_executadas.append(trade_protecao)
                return ordens_executadas
        
        # ============================================
        # VERIFICA CONFIRMAÇÃO DE CANDLE
        # ============================================
        if self.usar_confirmacao_candle and not is_candle_closed:
            # Atualiza sinais pendentes
            if preco <= banda_inf:
                self.candle_aberto_compra = True
            if preco >= banda_sup:
                self.candle_aberto_venda = True
            return []
        
        # ============================================
        # SINAIS DE COMPRA (Banda Inferior)
        # ============================================
        comprar = False
        motivo_compra = ""
        
        # Sinal principal: preço toca/cruza banda inferior
        if preco <= banda_inf and banda_valida and not self.em_posicao:
            # Filtro de tendência: não comprar em tendência de baixa forte
            if self.usar_filtro_tendencia and tendencia == 'BAIXA' and forca_tendencia > 0.3:
                self._log(f"Tendência de baixa ({forca_tendencia:.1f}), ignorando compra na banda inferior", "FILTRO")
            else:
                comprar = True
                motivo_compra = "BANDA_INFERIOR"
                self.sinais_compra['BANDA_INFERIOR'] += 1
        
        # Executa compra
        if comprar:
            quantidade, valor = self._calcular_quantidade(preco)
            
            if quantidade and quantidade > 0:
                trade = self.executar_compra(preco, quantidade, timestamp,
                                            motivo=motivo_compra,
                                            tendencia=tendencia,
                                            banda_superior=round(banda_sup, 2),
                                            media=round(media, 2),
                                            banda_inferior=round(banda_inf, 2),
                                            largura_banda=round(largura*100, 2))
                
                if trade:
                    self.em_posicao = True
                    self.preco_compra_medio = preco
                    self.quantidade_comprada_total = quantidade
                    self.maior_preco_posicao = preco
                    ordens_executadas.append(trade)
                    
                    self._log(f"SINAL DE COMPRA: {motivo_compra} em ${preco:.2f} (Banda Inf: ${banda_inf:.2f})", "SINAL")
                    
                    # Reseta confirmações
                    self.candle_aberto_compra = False
                    self.ultimo_sinal_compra = timestamp
        
        # ============================================
        # SINAIS DE VENDA (Banda Superior e Média)
        # ============================================
        if self.em_posicao:
            vender = False
            motivo_venda = ""
            quantidade_vender = 0
            
            # Sinal 1: Preço toca/cruza banda superior
            if preco >= banda_sup:
                vender = True
                motivo_venda = "BANDA_SUPERIOR"
                quantidade_vender = self.quantidade_comprada_total
                self.sinais_venda['BANDA_SUPERIOR'] += 1
            
            # Sinal 2: Venda parcial na média (reversão antecipada)
            elif (self.vender_na_media and self._cooldown_venda_media <= 0
                  and preco >= media and self.quantidade_comprada_total > 0):
                ganho_atual = (preco - self.preco_compra_medio) / self.preco_compra_medio
                
                # Só vende se tiver lucro
                if ganho_atual > 0:
                    vender = True
                    motivo_venda = "MEDIA"
                    quantidade_vender = self.quantidade_comprada_total * self.percentual_venda_media
                    self.sinais_venda['MEDIA'] += 1
                    self._cooldown_venda_media = self._cooldown_venda_media_max
                    
                    self._log(f"Venda parcial na média: {self.percentual_venda_media*100:.0f}% da posição", "SINAL")
            
            # Executa venda
            if vender and quantidade_vender > 0:
                # Ajusta quantidade para não exceder
                quantidade_vender = min(quantidade_vender, self.quantidade_comprada_total)
                
                if quantidade_vender > 0:
                    trade = self.executar_venda(preco, quantidade_vender, timestamp,
                                               motivo=motivo_venda,
                                               tendencia=tendencia,
                                               banda_superior=round(banda_sup, 2),
                                               media=round(media, 2),
                                               banda_inferior=round(banda_inf, 2),
                                               largura_banda=round(largura*100, 2))
                    
                    if trade:
                        self.quantidade_comprada_total -= quantidade_vender
                        
                        if self.quantidade_comprada_total <= 0.00000001:
                            self.em_posicao = False
                            self.quantidade_comprada_total = 0
                            self.preco_compra_medio = 0
                            self.maior_preco_posicao = 0
                            self._log(f"Posição totalmente vendida: {motivo_venda}", "SINAL")
                        else:
                            self._log(f"Venda parcial executada. Restam {self.quantidade_comprada_total:.8f} {self.symbol.replace('USDT', '')}", "SINAL")
                        
                        ordens_executadas.append(trade)
                        
                        # Reseta confirmações
                        self.candle_aberto_venda = False
                        self.ultimo_sinal_venda = timestamp
        
        return ordens_executadas
    
    def reset(self):
        """Reseta a estrategia"""
        super().reset()
        self.historico_bandas = deque(maxlen=1000)
        self.historico_volumes = deque(maxlen=1000)
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0
        self.perdas_consecutivas = 0
        self.cooldown_periods_counter = 0
        self.volume_atual = 0
        self.ultimo_sinal_compra = None
        self.ultimo_sinal_venda = None
        self.candle_aberto_compra = False
        self.candle_aberto_venda = False
        self._cooldown_venda_media = 0
        self.banda_largura_atual = 0
        self.sinais_compra = {'BANDA_INFERIOR': 0, 'REVERSAO_MEDIA': 0}
        self.sinais_venda = {'BANDA_SUPERIOR': 0, 'MEDIA': 0}
    
    def get_configuracao(self):
        """Retorna a configuracao atual da estrategia"""
        if self.percentual_por_trade:
            gestao_quantidade = f"{self.percentual_por_trade*100}% do saldo"
        else:
            simbolo_asset = self.symbol.replace('USDT', '')
            gestao_quantidade = f"{self.quantidade_por_trade} {simbolo_asset} (fixo)"
        
        return {
            'nome': 'Bollinger Bands (Versão Melhorada)',
            'descricao': 'Estratégia de reversão à média com Bandas de Bollinger. Inclui filtro de tendência, confirmação de candle, stop-loss, take-profit, trailing stop, venda parcial na média e cooldown.',
            'parametros': {
                'periodo': self.periodo,
                'desvios': self.desvios,
                'gestao_de_quantidade': gestao_quantidade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'filtro_tendencia': self.usar_filtro_tendencia,
                'confirmacao_candle': self.usar_confirmacao_candle,
                'banda_min_largura': f"{self.banda_min_largura*100}%",
                'banda_max_largura': f"{self.banda_max_largura*100}%",
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%",
                'vender_na_media': self.vender_na_media,
                'percentual_venda_media': f"{self.percentual_venda_media*100}%" if self.vender_na_media else 'N/A',
                'max_perdas_consecutivas': self.max_perdas_consecutivas,
                'cooldown_apos_perdas': self.cooldown_max_periods
            }
        }
    
    def get_estatisticas_bandas(self):
        """Retorna estatísticas das bandas"""
        if not self.historico_bandas:
            return {}
        
        larguras = [b['largura'] for b in self.historico_bandas]
        
        return {
            'largura_media': round(sum(larguras) / len(larguras) * 100, 2),
            'largura_max': round(max(larguras) * 100, 2),
            'largura_min': round(min(larguras) * 100, 2),
            'largura_atual': round(self.banda_largura_atual * 100, 2),
            'sinais_compra': self.sinais_compra,
            'sinais_venda': self.sinais_venda
        }
    
    def get_posicao_banda_atual(self):
        """Retorna a posição atual do preço nas bandas (0-1)"""
        if not self.historico_bandas:
            return 0.5
        
        ultima = self.historico_bandas[-1]
        preco_atual = self.historico_precos[-1]
        
        if ultima['banda_superior'] == ultima['banda_inferior']:
            return 0.5
        
        posicao = (preco_atual - ultima['banda_inferior']) / (ultima['banda_superior'] - ultima['banda_inferior'])
        return max(0, min(1, posicao))