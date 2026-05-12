import json
import os
from datetime import datetime
from collections import deque


class EstadoPersistente:
    def __init__(self, nome_arquivo: str = "estado_simulacao.json"):
        self.nome_arquivo = nome_arquivo

    def salvar(self, estrategia) -> str:
        estado = {
            'timestamp': datetime.now().isoformat(),
            'saldo_usdt': estrategia.saldo_usdt,
            'posicao': estrategia.posicao,
            'trades': estrategia.trades[-100:],
            'historico_precos': list(estrategia.historico_precos)[-1000:] if hasattr(estrategia, 'historico_precos') else [],
            'em_posicao': getattr(estrategia, 'em_posicao', False),
            'preco_compra_medio': getattr(estrategia, 'preco_compra_medio', 0),
            'quantidade_comprada_total': getattr(estrategia, 'quantidade_comprada_total', 0),
            'maior_preco_posicao': getattr(estrategia, 'maior_preco_posicao', 0),
            'ultimo_preco': getattr(estrategia, 'ultimo_preco', None),
            'ultimo_preco_conhecido': getattr(estrategia, 'ultimo_preco_conhecido', None),
            'perdas_consecutivas': getattr(estrategia, 'perdas_consecutivas', 0),
            'cooldown_periods_counter': getattr(estrategia, 'cooldown_periods_counter', 0),
        }

        os.makedirs('resultados', exist_ok=True)
        path = os.path.join('resultados', self.nome_arquivo)

        with open(path, 'w') as f:
            json.dump(estado, f, indent=2, default=str)

        return path

    def carregar(self, estrategia) -> bool:
        path = os.path.join('resultados', self.nome_arquivo)

        if not os.path.exists(path):
            return False

        with open(path, 'r') as f:
            estado = json.load(f)

        estrategia.saldo_usdt = estado.get('saldo_usdt', estrategia.saldo_usdt)
        estrategia.posicao = estado.get('posicao', estrategia.posicao)
        estrategia.trades = estado.get('trades', estrategia.trades)
        estrategia.em_posicao = estado.get('em_posicao', getattr(estrategia, 'em_posicao', False))
        estrategia.preco_compra_medio = estado.get('preco_compra_medio', getattr(estrategia, 'preco_compra_medio', 0))
        estrategia.quantidade_comprada_total = estado.get('quantidade_comprada_total', getattr(estrategia, 'quantidade_comprada_total', 0))
        estrategia.maior_preco_posicao = estado.get('maior_preco_posicao', getattr(estrategia, 'maior_preco_posicao', 0))

        if hasattr(estrategia, 'historico_precos'):
            precos = estado.get('historico_precos', [])
            estrategia.historico_precos = deque(precos, maxlen=2000)

        if 'ultimo_preco' in estado:
            estrategia.ultimo_preco = estado['ultimo_preco']
        if 'ultimo_preco_conhecido' in estado:
            estrategia.ultimo_preco_conhecido = estado['ultimo_preco_conhecido']
        if 'perdas_consecutivas' in estado:
            estrategia.perdas_consecutivas = estado['perdas_consecutivas']
        if 'cooldown_periods_counter' in estado:
            estrategia.cooldown_periods_counter = estado['cooldown_periods_counter']

        return True

    def existe(self) -> bool:
        return os.path.exists(os.path.join('resultados', self.nome_arquivo))

    def limpar(self) -> None:
        path = os.path.join('resultados', self.nome_arquivo)
        if os.path.exists(path):
            os.remove(path)
