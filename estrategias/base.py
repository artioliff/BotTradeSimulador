# estrategias/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from collections import deque
import time

class EstrategiaBase(ABC):
    """
    Classe base abstrata para todas as estrategias de trading.
    Todas as estrategias devem herdar desta classe e implementar seus metodos.
    """
    
    def __init__(self, symbol, saldo_inicial=10000):
        self.symbol = symbol
        self.saldo_inicial = saldo_inicial
        self.timestamps_ordens = deque(maxlen=10)
        self.reset()
    
    def reset(self):
        """Reseta o estado da estrategia para uma nova simulacao"""
        self.trades = []
        self.saldo_usdt = self.saldo_inicial
        self.posicao = 0
        self.ultimo_preco = None
        self.client = None  # Será definido depois se necessário
    
    # ============================================
    # METODOS PARA SALDO REAL DA BINANCE
    # ============================================
    
    def set_client(self, client):
        """Define o cliente da Binance para consultas de saldo"""
        self.client = client
    
    def obter_saldo_real_usdt(self):
        """Consulta o saldo REAL de USDT na conta Spot da Binance."""
        if not self.client:
            print("  Cliente não configurado. Use set_client() primeiro.")
            return self.saldo_usdt
        
        try:
            account_info = self.client.get_account()
            for balance in account_info['balances']:
                if balance['asset'] == 'USDT':
                    saldo_disponivel = float(balance['free'])
                    print(f"  Saldo real da conta: ${saldo_disponivel:.2f} USDT")
                    if saldo_disponivel != self.saldo_usdt:
                        print(f"  Sincronizando saldo: ${self.saldo_usdt:.2f} -> ${saldo_disponivel:.2f}")
                        self.saldo_usdt = saldo_disponivel
                    return saldo_disponivel
            print("  USDT não encontrado na conta")
            return self.saldo_usdt
        except Exception as e:
            print(f"  Erro ao consultar saldo: {e}")
            return self.saldo_usdt
    
    def atualizar_saldo_real(self):
        """Atualiza o saldo real da conta sem retornar valor."""
        if self.client:
            self.obter_saldo_real_usdt()
    
    def sincronizar_saldo_apos_trade(self, tipo, preco, quantidade):
        """Sincroniza o saldo real APÓS um trade (simulado)."""
        if self.client:
            saldo_real = self.obter_saldo_real_usdt()
            diferenca = saldo_real - self.saldo_usdt
            if abs(diferenca) > 0.01:
                print(f"  [ALERTA] Diferença entre saldo simulado e real: ${diferenca:+.2f}")
                print(f"    Saldo simulado: ${self.saldo_usdt:.2f}")
                print(f"    Saldo real: ${saldo_real:.2f}")
    
    def calcular_rsi_wilder(self, precos, periodo=14):
        """Calcula o RSI usando o metodo suavizado de Wilder"""
        if len(precos) < periodo + 1:
            return 50
        
        ganhos = []
        perdas = []
        
        for i in range(1, len(precos)):
            variacao = precos[i] - precos[i-1]
            if variacao >= 0:
                ganhos.append(variacao)
                perdas.append(0)
            else:
                ganhos.append(0)
                perdas.append(abs(variacao))
        
        ganho_medio = sum(ganhos[:periodo]) / periodo
        perda_media = sum(perdas[:periodo]) / periodo
        
        for i in range(periodo, len(ganhos)):
            ganho_medio = (ganho_medio * (periodo - 1) + ganhos[i]) / periodo
            perda_media = (perda_media * (periodo - 1) + perdas[i]) / periodo
        
        if perda_media == 0:
            return 100
        
        rs = ganho_medio / perda_media
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def _verificar_rate_limit(self):
        """Verifica se pode executar ordem (Binance: 10 ordens/segundo)"""
        agora = time.time()
        while self.timestamps_ordens and agora - self.timestamps_ordens[0] > 1.0:
            self.timestamps_ordens.popleft()
        
        if len(self.timestamps_ordens) >= 10:
            time.sleep(0.1)
            return self._verificar_rate_limit()
        
        self.timestamps_ordens.append(agora)
        return True
    
    # ============================================
    # METODOS ABSTRATOS E PRINCIPAIS
    # ============================================
    
    def processar_preco(self, preco, timestamp):
        """Processa cada atualizacao de preco (opcional)"""
        return []

    @abstractmethod
    def get_configuracao(self):
        """Retorna a configuracao atual da estrategia"""
        pass
    
    def registrar_trade(self, tipo, preco, quantidade, timestamp=None, **kwargs):
        """Registra um trade executado"""
        if timestamp is None:
            timestamp = datetime.now()
            
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
    
    def executar_compra(self, preco, quantidade, timestamp=None, **kwargs):
        """Executa uma compra simulada"""
        self._verificar_rate_limit()
        custo = preco * quantidade
        if custo <= self.saldo_usdt:
            self.saldo_usdt -= custo
            self.posicao += quantidade
            trade = self.registrar_trade('BUY', preco, quantidade, timestamp, custo=custo, **kwargs)
            time_str = trade['timestamp'].strftime('%H:%M:%S') if hasattr(trade['timestamp'], 'strftime') else str(trade['timestamp'])
            print(f"[{time_str}] COMPRA: {quantidade} @ ${preco:.2f} | Saldo: ${self.saldo_usdt:.2f} | Posicao: {self.posicao:.4f}")
            return trade
        else:
            print(f"Saldo insuficiente para comprar {quantidade} @ ${preco:.2f}")
            return None
    
    def executar_venda(self, preco, quantidade, timestamp=None, **kwargs):
        """Executa uma venda simulada"""
        self._verificar_rate_limit()
        if quantidade <= self.posicao:
            self.saldo_usdt += preco * quantidade
            self.posicao -= quantidade
            trade = self.registrar_trade('SELL', preco, quantidade, timestamp, receita=preco * quantidade, **kwargs)
            time_str = trade['timestamp'].strftime('%H:%M:%S') if hasattr(trade['timestamp'], 'strftime') else str(trade['timestamp'])
            print(f"[{time_str}] VENDA: {quantidade} @ ${preco:.2f} | Saldo: ${self.saldo_usdt:.2f} | Posicao: {self.posicao:.4f}")
            return trade
        else:
            print(f"Posicao insuficiente para vender {quantidade}")
            return None
    
    def get_relatorio(self):
        """Gera relatorio completo da simulacao"""
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
        
        # Separa compras e vendas
        trades_compra = [t for t in self.trades if t['tipo'] == 'BUY']
        trades_venda = [t for t in self.trades if t['tipo'] == 'SELL']
        
        # Calcula usando preco * quantidade diretamente
        total_comprado = sum(t['preco'] * t['quantidade'] for t in trades_compra)
        total_vendido = sum(t['preco'] * t['quantidade'] for t in trades_venda)
        
        lucro_total = total_vendido - total_comprado
        
        # Taxa de acerto baseada em pares compra/venda sequenciais
        trades_acertados = 0
        for i in range(min(len(trades_venda), len(trades_compra))):
            if trades_venda[i]['preco'] > trades_compra[i]['preco']:
                trades_acertados += 1
        
        taxa_acerto = (trades_acertados / len(trades_venda) * 100) if trades_venda else 0
        
        # Valor total do portfolio
        valor_total_portfolio = self.saldo_usdt
        if self.ultimo_preco and self.posicao > 0:
            valor_total_portfolio += self.posicao * self.ultimo_preco
        
        return {
            'total_trades': len(self.trades),
            'total_compras': len(trades_compra),
            'total_vendas': len(trades_venda),
            'total_comprado_usdt': round(total_comprado, 2),
            'total_vendido_usdt': round(total_vendido, 2),
            'lucro_usdt': round(lucro_total, 2),
            'taxa_acerto': round(taxa_acerto, 2),
            'saldo_final_usdt': round(self.saldo_usdt, 2),
            'posicao_final': round(self.posicao, 4),
            'valor_total_portfolio': round(valor_total_portfolio, 2),
            'trades_df': df_trades
        }

    def resetar_simulacao(self):
        """Reseta a simulacao para comecar do zero"""
        self.reset()