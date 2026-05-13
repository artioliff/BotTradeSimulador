from abc import ABC, abstractmethod
from datetime import datetime
from collections import deque
import time
import logging

logger = logging.getLogger("TradeSimulado")


class EstrategiaBase(ABC):
    def __init__(self, symbol: str, saldo_inicial: float = 10000, debug: bool = False):
        self.symbol = symbol
        self.saldo_inicial = saldo_inicial
        self.debug = debug
        self.timestamps_ordens = deque(maxlen=10)
        self.live_mode: bool = False
        self.reset()

    def _log(self, msg: str, nivel: str = "INFO") -> None:
        levels = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "AVISO": logging.WARNING,
                  "ALERTA": logging.WARNING, "ERRO": logging.ERROR, "SUCESSO": logging.INFO,
                  "SINAL": logging.INFO, "FILTRO": logging.DEBUG, "RATE_LIMIT": logging.WARNING}
        level = levels.get(nivel, logging.INFO)
        if self.debug or level >= logging.WARNING:
            logger.log(level, "%s", msg)

    def reset(self) -> None:
        self.trades: list[dict] = []
        self.saldo_usdt: float = float(self.saldo_inicial)
        self.posicao: float = 0.0
        self.ultimo_preco: float | None = None
        self.ultimo_preco_conhecido: float | None = None
        self.historico_precos = deque(maxlen=2000)
        self.em_posicao: bool = False
        self.client = None

    def set_client(self, client) -> None:
        self.client = client
        self._log("Cliente da Binance configurado")

    def obter_saldo_real_usdt(self) -> float:
        if not self.client:
            self._log("Cliente não configurado. Use set_client() primeiro.", "AVISO")
            return self.saldo_usdt

        try:
            account_info = self.client.get_account()
            for balance in account_info['balances']:
                if balance['asset'] == 'USDT':
                    saldo_disponivel = float(balance['free'])
                    self._log(f"Saldo real da conta: ${saldo_disponivel:.2f} USDT")

                    if abs(saldo_disponivel - self.saldo_usdt) > 0.01:
                        self._log(f"Sincronizando saldo: ${self.saldo_usdt:.2f} -> ${saldo_disponivel:.2f}")
                        self.saldo_usdt = saldo_disponivel

                    return saldo_disponivel

            self._log("USDT não encontrado na conta", "AVISO")
            return self.saldo_usdt

        except Exception as e:
            self._log(f"Erro ao consultar saldo: {e}", "ERRO")
            return self.saldo_usdt

    def atualizar_saldo_real(self) -> None:
        if self.client:
            self.obter_saldo_real_usdt()

    def sincronizar_saldo_apos_trade(self, tipo: str, preco: float, quantidade: float) -> None:
        if self.client:
            saldo_real = self.obter_saldo_real_usdt()
            diferenca = saldo_real - self.saldo_usdt
            if abs(diferenca) > 0.01:
                self._log(f"[ALERTA] Diferença entre saldo simulado e real: ${diferenca:+.2f}", "ALERTA")
                self._log(f"    Saldo simulado: ${self.saldo_usdt:.2f}")
                self._log(f"    Saldo real: ${saldo_real:.2f}")

    def calcular_rsi_wilder(self, precos, periodo: int = 14) -> float:
        if hasattr(precos, '__len__') and not isinstance(precos, list):
            precos_lista = list(precos)
        else:
            precos_lista = precos

        if len(precos_lista) < periodo + 1:
            return 50.0

        ganhos = []
        perdas = []

        for i in range(1, len(precos_lista)):
            variacao = precos_lista[i] - precos_lista[i-1]
            if variacao >= 0:
                ganhos.append(variacao)
                perdas.append(0.0)
            else:
                ganhos.append(0.0)
                perdas.append(abs(variacao))

        ganho_medio = sum(ganhos[:periodo]) / periodo
        perda_media = sum(perdas[:periodo]) / periodo

        for i in range(periodo, len(ganhos)):
            ganho_medio = (ganho_medio * (periodo - 1) + ganhos[i]) / periodo
            perda_media = (perda_media * (periodo - 1) + perdas[i]) / periodo

        if perda_media == 0:
            return 100.0

        rs = ganho_medio / perda_media
        rsi = 100 - (100 / (1 + rs))

        return round(rsi, 2)

    def calcular_media_movel_simples(self, precos, periodo: int) -> float | None:
        if len(precos) < periodo:
            return None

        precos_lista = list(precos) if hasattr(precos, '__len__') and not isinstance(precos, list) else precos
        return sum(precos_lista[-periodo:]) / periodo

    def calcular_media_movel_exponencial(self, precos, periodo: int) -> float | None:
        if len(precos) < periodo:
            return None

        precos_lista = list(precos) if hasattr(precos, '__len__') and not isinstance(precos, list) else precos
        k = 2 / (periodo + 1)
        ema = sum(precos_lista[:periodo]) / periodo

        for preco in precos_lista[periodo:]:
            ema = (preco * k) + (ema * (1 - k))

        return ema

    def calcular_volatilidade(self, precos, periodo: int = 20) -> float | None:
        if len(precos) < periodo + 1:
            return None

        precos_lista = list(precos) if hasattr(precos, '__len__') and not isinstance(precos, list) else precos

        returns = []
        for i in range(1, len(precos_lista)):
            returns.append((precos_lista[i] - precos_lista[i-1]) / precos_lista[i-1])

        if len(returns) < periodo:
            return None

        ultimos_returns = returns[-periodo:]
        media = sum(ultimos_returns) / periodo
        variancia = sum((r - media) ** 2 for r in ultimos_returns) / periodo

        return variancia ** 0.5

    def _verificar_rate_limit(self) -> bool:
        if not self.live_mode:
            return True

        agora = time.time()
        tentativas = 0

        while tentativas < 20:
            while self.timestamps_ordens and agora - self.timestamps_ordens[0] > 1.0:
                self.timestamps_ordens.popleft()

            if len(self.timestamps_ordens) < 10:
                self.timestamps_ordens.append(agora)
                return True

            tentativas += 1
            self._log(f"Rate limit atingido, aguardando 0.1s... (tentativa {tentativas}/20)", "RATE_LIMIT")
            time.sleep(0.1)
            agora = time.time()

        self._log("Rate limit estourou apos 20 tentativas", "ERRO")
        return False

    def em_cooldown(self, ultimo_trade_timestamp, cooldown_segundos: int = 60) -> bool:
        if ultimo_trade_timestamp is None:
            return False

        tempo_decorrido = (datetime.now() - ultimo_trade_timestamp).total_seconds()
        return tempo_decorrido < cooldown_segundos

    def _verificar_stop_take_trailing(self, preco: float, timestamp, stop_loss_percent: float,
                                       take_profit_percent: float, trailing_stop_percent: float,
                                       **kwargs):
        if not self.em_posicao or self.preco_compra_medio <= 0:
            return None

        ganho_percentual = (preco - self.preco_compra_medio) / self.preco_compra_medio

        tipo = None
        if ganho_percentual <= -stop_loss_percent:
            tipo = 'STOP_LOSS'
        elif ganho_percentual >= take_profit_percent:
            tipo = 'TAKE_PROFIT'
        elif trailing_stop_percent > 0:
            if preco > self.maior_preco_posicao:
                self.maior_preco_posicao = preco
            if self.maior_preco_posicao > self.preco_compra_medio:
                queda_do_pico = (self.maior_preco_posicao - preco) / self.maior_preco_posicao
                if queda_do_pico >= trailing_stop_percent:
                    tipo = 'TRAILING_STOP'

        if tipo is None:
            return None

        trade = self.executar_venda(preco, self.quantidade_comprada_total, timestamp,
                                   motivo=tipo, ganho_percentual=round(ganho_percentual*100, 2),
                                   **kwargs)
        if trade:
            self.em_posicao = False
            self.quantidade_comprada_total = 0
            self.preco_compra_medio = 0
            self.maior_preco_posicao = 0

        return trade

    def registrar_trade(self, tipo: str, preco: float, quantidade: float,
                        timestamp=None, **kwargs) -> dict:
        if timestamp is None:
            timestamp = datetime.now()

        self.ultimo_preco_conhecido = preco

        trade = {
            'timestamp': timestamp,
            'tipo': tipo,
            'preco': preco,
            'quantidade': quantidade,
            'custo': preco * quantidade if tipo == 'BUY' else 0,
            'receita': preco * quantidade if tipo == 'SELL' else 0,
            'saldo_usdt': self.saldo_usdt,
            'posicao': self.posicao
        }
        trade.update(kwargs)
        self.trades.append(trade)

        return trade

    def executar_compra(self, preco: float, quantidade: float, timestamp=None, **kwargs):
        self._verificar_rate_limit()

        if self.live_mode and self.client:
            try:
                quote_qty = round(preco * quantidade, 2)
                order = self.client.order_market_buy(
                    symbol=self.symbol,
                    quoteOrderQty=quote_qty
                )
                if order['status'] == 'FILLED':
                    executed_qty = float(order['executedQty'])
                    spent_qty = float(order['cummulativeQuoteQty'])
                    actual_price = spent_qty / executed_qty if executed_qty > 0 else preco

                    self.saldo_usdt -= spent_qty
                    self.posicao += executed_qty
                    self.em_posicao = True
                    self.ultimo_preco = actual_price

                    trade = self.registrar_trade('BUY', actual_price, executed_qty, timestamp,
                                                 custo=spent_qty, order_id=order['orderId'], **kwargs)

                    time_str = trade['timestamp'].strftime('%H:%M:%S') if hasattr(trade['timestamp'], 'strftime') else str(trade['timestamp'])
                    print(f"[{time_str}] COMPRA REAL: {executed_qty:.8f} @ ${actual_price:.2f} | Gasto: ${spent_qty:.2f} | OrderID: {order['orderId']}")

                    return trade
                else:
                    self._log(f"Ordem de compra nao foi totalmente preenchida. Status: {order['status']}", "ERRO")
                    return None
            except Exception as e:
                self._log(f"Erro ao executar ordem de compra real: {e}", "ERRO")
                print(f"  [ERRO] Falha na ordem de compra real: {e}")
                return None

        custo = preco * quantidade

        if custo <= self.saldo_usdt + 0.0001:
            self.saldo_usdt -= custo
            self.posicao += quantidade
            self.em_posicao = True
            self.ultimo_preco = preco

            trade = self.registrar_trade('BUY', preco, quantidade, timestamp, custo=custo, **kwargs)

            time_str = trade['timestamp'].strftime('%H:%M:%S') if hasattr(trade['timestamp'], 'strftime') else str(trade['timestamp'])
            print(f"[{time_str}] COMPRA: {quantidade:.8f} @ ${preco:.2f} | Saldo: ${self.saldo_usdt:.2f} | Posicao: {self.posicao:.8f}")

            self.sincronizar_saldo_apos_trade('BUY', preco, quantidade)

            return trade
        else:
            self._log(f"Saldo insuficiente! Necessário ${custo:.2f}, disponível ${self.saldo_usdt:.2f}", "ERRO")
            print(f"  [ERRO] Saldo insuficiente para comprar {quantidade:.8f} @ ${preco:.2f}")
            return None

    def executar_venda(self, preco: float, quantidade: float, timestamp=None, **kwargs):
        self._verificar_rate_limit()

        if self.live_mode and self.client:
            try:
                order = self.client.order_market_sell(
                    symbol=self.symbol,
                    quantity=quantidade
                )
                if order['status'] == 'FILLED':
                    executed_qty = float(order['executedQty'])
                    received_qty = float(order['cummulativeQuoteQty'])
                    actual_price = received_qty / executed_qty if executed_qty > 0 else preco

                    self.saldo_usdt += received_qty
                    self.posicao -= executed_qty

                    if self.posicao <= 0.00000001:
                        self.em_posicao = False
                        self.posicao = 0.0

                    self.ultimo_preco = actual_price

                    trade = self.registrar_trade('SELL', actual_price, executed_qty, timestamp,
                                                 receita=received_qty, order_id=order['orderId'], **kwargs)

                    time_str = trade['timestamp'].strftime('%H:%M:%S') if hasattr(trade['timestamp'], 'strftime') else str(trade['timestamp'])
                    print(f"[{time_str}] VENDA REAL: {executed_qty:.8f} @ ${actual_price:.2f} | Recebido: ${received_qty:.2f} | OrderID: {order['orderId']}")

                    return trade
                else:
                    self._log(f"Ordem de venda nao foi totalmente preenchida. Status: {order['status']}", "ERRO")
                    return None
            except Exception as e:
                self._log(f"Erro ao executar ordem de venda real: {e}", "ERRO")
                print(f"  [ERRO] Falha na ordem de venda real: {e}")
                return None

        if quantidade <= self.posicao + 0.00000001:
            self.saldo_usdt += preco * quantidade
            self.posicao -= quantidade
            self.ultimo_preco = preco

            if self.posicao <= 0.00000001:
                self.em_posicao = False
                self.posicao = 0.0

            trade = self.registrar_trade('SELL', preco, quantidade, timestamp, receita=preco * quantidade, **kwargs)

            time_str = trade['timestamp'].strftime('%H:%M:%S') if hasattr(trade['timestamp'], 'strftime') else str(trade['timestamp'])
            print(f"[{time_str}] VENDA: {quantidade:.8f} @ ${preco:.2f} | Saldo: ${self.saldo_usdt:.2f} | Posicao: {self.posicao:.8f}")

            self.sincronizar_saldo_apos_trade('SELL', preco, quantidade)

            return trade
        else:
            self._log(f"Posicao insuficiente! Necessário vender {quantidade:.8f}, disponível {self.posicao:.8f}", "ERRO")
            print(f"  [ERRO] Posicao insuficiente para vender {quantidade:.8f}")
            return None

    def get_relatorio(self):
        if not self.trades:
            return {
                'total_trades': 0,
                'mensagem': 'Nenhum trade executado'
            }

        df_trades = None
        try:
            import pandas as pd
            df_trades = pd.DataFrame(self.trades)
        except ImportError:
            pass

        trades_compra = [t for t in self.trades if t['tipo'] == 'BUY']
        trades_venda = [t for t in self.trades if t['tipo'] == 'SELL']

        total_comprado = sum(t['preco'] * t['quantidade'] for t in trades_compra)
        total_vendido = sum(t['preco'] * t['quantidade'] for t in trades_venda)

        lucro_total = total_vendido - total_comprado

        trades_acertados = 0
        for i in range(min(len(trades_venda), len(trades_compra))):
            if trades_venda[i]['preco'] > trades_compra[i]['preco']:
                trades_acertados += 1

        taxa_acerto = (trades_acertados / len(trades_venda) * 100) if trades_venda else 0

        valor_total_portfolio = self.saldo_usdt

        preco_para_calculo = self.ultimo_preco if self.ultimo_preco is not None else self.ultimo_preco_conhecido

        if preco_para_calculo and self.posicao > 0:
            valor_total_portfolio += self.posicao * preco_para_calculo

        return {
            'total_trades': len(self.trades),
            'total_compras': len(trades_compra),
            'total_vendas': len(trades_venda),
            'total_comprado_usdt': round(total_comprado, 2),
            'total_vendido_usdt': round(total_vendido, 2),
            'lucro_usdt': round(lucro_total, 2),
            'taxa_acerto': round(taxa_acerto, 2),
            'saldo_final_usdt': round(self.saldo_usdt, 2),
            'posicao_final': round(self.posicao, 8),
            'valor_total_portfolio': round(valor_total_portfolio, 2),
            'retorno_percentual': round(((valor_total_portfolio - self.saldo_inicial) / self.saldo_inicial) * 100, 2),
            'trades_df': df_trades
        }

    def get_resumo_trades(self) -> str:
        if not self.trades:
            return "Nenhum trade executado."

        resumo = []
        resumo.append(f"\n{'='*60}")
        resumo.append(f"RESUMO DE TRADES - {self.symbol}")
        resumo.append(f"{'='*60}")

        for i, trade in enumerate(self.trades):
            tipo = trade['tipo']
            preco = trade['preco']
            qtd = trade['quantidade']
            ts = trade['timestamp']

            if isinstance(ts, datetime):
                ts = ts.strftime('%Y-%m-%d %H:%M:%S')

            resumo.append(f"#{i+1:3d} | {tipo:4s} | {ts} | Preço: ${preco:.2f} | Qtd: {qtd:.8f}")

        return "\n".join(resumo)

    def print_resumo(self) -> None:
        relatorio = self.get_relatorio()

        print("\n" + "="*60)
        print(f"RESUMO DA SIMULAÇÃO - {self.symbol}")
        print("="*60)

        if relatorio.get('total_trades', 0) == 0:
            print("Nenhum trade foi executado.")
            return

        print(f"Total de trades: {relatorio['total_trades']}")
        print(f"  - Compras: {relatorio['total_compras']}")
        print(f"  - Vendas: {relatorio['total_vendas']}")
        print(f"Total comprado: ${relatorio['total_comprado_usdt']:.2f}")
        print(f"Total vendido: ${relatorio['total_vendido_usdt']:.2f}")
        print(f"LUCRO/PREJUÍZO: ${relatorio['lucro_usdt']:.2f}")
        print(f"Taxa de acerto: {relatorio['taxa_acerto']:.2f}%")
        print(f"Saldo final USDT: ${relatorio['saldo_final_usdt']:.2f}")
        print(f"Posição final: {relatorio['posicao_final']:.8f}")
        print(f"Valor total do portfolio: ${relatorio['valor_total_portfolio']:.2f}")
        print(f"Retorno total: {relatorio['retorno_percentual']:.2f}%")
        print("="*60)

    def resetar_simulacao(self) -> None:
        self.reset()
        self._log("Simulação resetada completamente")

    @abstractmethod
    def get_configuracao(self):
        pass

    def processar_preco(self, preco: float, timestamp, **kwargs):
        return []
