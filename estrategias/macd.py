from .base import EstrategiaBase
from collections import deque


class MACDStrategy(EstrategiaBase):
    def __init__(self, symbol: str, fast_period: int = 12, slow_period: int = 26,
                 signal_period: int = 9, quantidade_por_trade: float = 0.001,
                 saldo_inicial: float = 10000,
                 stop_loss_percent: float = 0.02, take_profit_percent: float = 0.03,
                 trailing_stop_percent: float = 0.01):
        super().__init__(symbol, saldo_inicial)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.quantidade_por_trade = quantidade_por_trade
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.trailing_stop_percent = trailing_stop_percent
        self.historico_macd = deque(maxlen=500)
        self.em_posicao: bool = False
        self.preco_compra_medio: float = 0
        self.quantidade_comprada_total: float = 0
        self.maior_preco_posicao: float = 0

    def calcular_macd(self, precos):
        if len(precos) < self.slow_period + self.signal_period:
            return None, None, None

        ema_fast = self._calcular_ema(precos, self.fast_period)
        ema_slow = self._calcular_ema(precos, self.slow_period)

        macd_line = ema_fast - ema_slow

        macd_values = [m[0] for m in self.historico_macd]
        macd_values.append(macd_line)

        if len(macd_values) >= self.signal_period:
            macd_signal = self._calcular_ema(macd_values, self.signal_period)
        else:
            macd_signal = macd_line

        histograma = macd_line - macd_signal

        return macd_line, macd_signal, histograma

    def _calcular_ema(self, precos, periodo: int) -> float:
        if len(precos) < periodo:
            return precos[-1] if precos else 0

        precos_lista = list(precos) if not isinstance(precos, list) else precos
        multiplicador = 2 / (periodo + 1)
        ema = sum(precos_lista[:periodo]) / periodo

        for preco in precos_lista[periodo:]:
            ema = (preco - ema) * multiplicador + ema

        return ema

    def processar_preco(self, preco: float, timestamp, **kwargs):
        self.historico_precos.append(preco)

        if len(self.historico_precos) < self.slow_period + self.signal_period:
            return []

        macd, signal, hist = self.calcular_macd(self.historico_precos)

        if macd is None:
            return []

        trade = self._verificar_stop_take_trailing(
            preco, timestamp, self.stop_loss_percent, self.take_profit_percent,
            self.trailing_stop_percent, macd=round(macd, 4), sinal=round(signal, 4))
        if trade:
            return [trade]

        ordens = []

        if len(self.historico_macd) > 0:
            macd_anterior, signal_anterior = self.historico_macd[-1][:2]

            if macd_anterior <= signal_anterior and macd > signal and not self.em_posicao:
                trade = self.executar_compra(preco, self.quantidade_por_trade, timestamp,
                                            macd=round(macd, 4), sinal=round(signal, 4))
                if trade:
                    self.em_posicao = True
                    self.preco_compra_medio = preco
                    self.quantidade_comprada_total = self.quantidade_por_trade
                    self.maior_preco_posicao = preco
                    ordens.append(trade)

            elif macd_anterior >= signal_anterior and macd < signal and self.em_posicao:
                trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                           macd=round(macd, 4), sinal=round(signal, 4))
                if trade:
                    self.em_posicao = False
                    self.quantidade_comprada_total = 0
                    self.preco_compra_medio = 0
                    self.maior_preco_posicao = 0
                    ordens.append(trade)

        self.historico_macd.append((macd, signal, hist))
        return ordens

    def reset(self):
        super().reset()
        self.historico_macd = deque(maxlen=500)
        self.em_posicao = False
        self.preco_compra_medio = 0
        self.quantidade_comprada_total = 0
        self.maior_preco_posicao = 0

    def get_configuracao(self):
        return {
            'nome': 'MACD',
            'descricao': 'Compra no cruzamento MACD acima do sinal, vende no cruzamento abaixo.',
            'parametros': {
                'periodo_rapido': self.fast_period,
                'periodo_lento': self.slow_period,
                'periodo_sinal': self.signal_period,
                'quantidade_por_trade': self.quantidade_por_trade,
                'saldo_inicial_usdt': self.saldo_inicial,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'take_profit_percentual': f"{self.take_profit_percent * 100}%",
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%"
            }
        }
