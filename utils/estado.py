import json
import os
from datetime import datetime

class EstadoPersistente:
    def __init__(self, nome_arquivo="estado_simulacao.json"):
        self.nome_arquivo = nome_arquivo
    
    def salvar(self, estrategia):
        """Salva estado da estrategia"""
        estado = {
            'timestamp': datetime.now().isoformat(),
            'saldo_usdt': estrategia.saldo_usdt,
            'posicao': estrategia.posicao,
            'trades': estrategia.trades[-100:],
            'historico_precos': estrategia.historico_precos[-1000:] if hasattr(estrategia, 'historico_precos') else [],
            'em_posicao': getattr(estrategia, 'em_posicao', False),
            'preco_compra_medio': getattr(estrategia, 'preco_compra_medio', 0)
        }
        
        os.makedirs('resultados', exist_ok=True)
        path = os.path.join('resultados', self.nome_arquivo)
        
        with open(path, 'w') as f:
            json.dump(estado, f, indent=2, default=str)
        
        return path
    
    def carregar(self, estrategia):
        """Carrega estado salvo"""
        path = os.path.join('resultados', self.nome_arquivo)
        
        if os.path.exists(path):
            with open(path, 'r') as f:
                estado = json.load(f)
            
            estrategia.saldo_usdt = estado['saldo_usdt']
            estrategia.posicao = estado['posicao']
            estrategia.trades = estado['trades']
            
            if hasattr(estrategia, 'historico_precos'):
                estrategia.historico_precos = list(estado['historico_precos'])
            
            if 'em_posicao' in estado:
                estrategia.em_posicao = estado['em_posicao']
            if 'preco_compra_medio' in estado:
                estrategia.preco_compra_medio = estado['preco_compra_medio']
            
            return True
        return False
    
    def existe(self):
        """Verifica se existe estado salvo"""
        return os.path.exists(os.path.join('resultados', self.nome_arquivo))