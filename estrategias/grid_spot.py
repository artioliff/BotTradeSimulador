from .base import EstrategiaBase
from collections import deque
from datetime import datetime


class GridSpotStrategy(EstrategiaBase):
    def __init__(self, symbol: str, num_grids: int = 10,
                 spacing_percent: float = 0.01,
                 quantidade_por_ordem: float = 0.001,
                 saldo_inicial: float = 10000,
                 recomprar_apos_venda: bool = True,
                 max_grids_ativos: int = 5,
                 stop_loss_percent: float = 0.05,
                 usar_trailing_stop: bool = False,
                 trailing_stop_percent: float = 0.02,
                 debug: bool = False):
        super().__init__(symbol, saldo_inicial, debug=debug)
        self.num_grids = num_grids
        self.spacing_percent = spacing_percent
        self.quantidade_por_ordem = quantidade_por_ordem
        self.recomprar_apos_venda = recomprar_apos_venda
        self.max_grids_ativos = max_grids_ativos
        self.stop_loss_percent = stop_loss_percent
        self.usar_trailing_stop = usar_trailing_stop
        self.trailing_stop_percent = trailing_stop_percent

        self.niveis_compra: list[dict] = []
        self.niveis_venda: list[dict] = []
        self.ordens_ativas: list[dict] = []
        self.historico_execucoes: list[dict] = []
        self.grids_calculados: bool = False

        self.preco_entrada_grid: float | None = None
        self.menor_preco_grid: float = float('inf')
        self.maior_preco_grid: float = 0
        self.ultima_recomposicao = None

        self.total_compras_grid: int = 0
        self.total_vendas_grid: int = 0
        self.lucro_grid: float = 0.0

    def _calcular_niveis_grid(self, preco_atual: float):
        niveis_compra = []
        niveis_venda = []

        grids_por_lado = self.num_grids // 2

        for i in range(1, grids_por_lado + 1):
            preco = preco_atual * (1 - self.spacing_percent * i)
            niveis_compra.append({
                'id': f"BUY_{i}",
                'nivel': i,
                'preco': round(preco, 8),
                'tipo': 'BUY',
                'quantidade': self.quantidade_por_ordem,
                'executada': False,
                'timestamp_execucao': None,
                'preco_execucao': None
            })

        for i in range(1, grids_por_lado + 1):
            preco = preco_atual * (1 + self.spacing_percent * i)
            niveis_venda.append({
                'id': f"SELL_{i}",
                'nivel': i,
                'preco': round(preco, 8),
                'tipo': 'SELL',
                'quantidade': self.quantidade_por_ordem,
                'executada': False,
                'timestamp_execucao': None,
                'preco_execucao': None
            })

        niveis_compra.sort(key=lambda x: x['preco'], reverse=True)
        niveis_venda.sort(key=lambda x: x['preco'])

        return niveis_compra, niveis_venda

    def _recompor_grid(self, preco_atual: float):
        for nivel in self.niveis_compra:
            if nivel['executada']:
                nivel['executada'] = False
                self._log(f"Recompondo compra nivel {nivel['nivel']} em ${nivel['preco']:.2f}")

        for nivel in self.niveis_venda:
            if nivel['executada']:
                nivel['executada'] = False
                self._log(f"Recompondo venda nivel {nivel['nivel']} em ${nivel['preco']:.2f}")

        self.ultima_recomposicao = preco_atual

    def _verificar_stop_loss_grid(self, preco_atual: float) -> bool:
        if not self.em_posicao or self.preco_entrada_grid is None:
            return False

        perda_percentual = (preco_atual - self.preco_entrada_grid) / self.preco_entrada_grid

        if perda_percentual <= -self.stop_loss_percent:
            self._log(f"Stop-loss do grid acionado! Perda de {abs(perda_percentual)*100:.2f}%")

            trade = self.executar_venda(preco_atual, self.posicao,
                                       timestamp=datetime.now(),
                                       motivo='STOP_LOSS_GRID')
            if trade:
                self.em_posicao = False
                self.preco_entrada_grid = None
                return True

        return False

    def _verificar_trailing_stop(self, preco_atual: float) -> bool:
        if not self.usar_trailing_stop or not self.em_posicao:
            return False

        if preco_atual > self.maior_preco_grid:
            self.maior_preco_grid = preco_atual

        if self.maior_preco_grid > self.preco_entrada_grid:
            queda_do_pico = (self.maior_preco_grid - preco_atual) / self.maior_preco_grid

            if queda_do_pico >= self.trailing_stop_percent:
                ganho_atual = (preco_atual - self.preco_entrada_grid) / self.preco_entrada_grid
                self._log(f"Trailing stop acionado! Lucro preservado: {ganho_atual*100:.2f}%")

                trade = self.executar_venda(preco_atual, self.posicao,
                                           timestamp=datetime.now(),
                                           motivo='TRAILING_STOP_GRID')
                if trade:
                    self.em_posicao = False
                    self.preco_entrada_grid = None
                    return True

        return False

    def processar_preco(self, preco: float, timestamp, **kwargs):
        self.ultimo_preco = preco
        self.historico_precos.append(preco)

        if not self.grids_calculados:
            self.niveis_compra, self.niveis_venda = self._calcular_niveis_grid(preco)
            self.grids_calculados = True
            self._print_configuracao(preco)
            self.preco_entrada_grid = preco
            self.menor_preco_grid = preco
            self.maior_preco_grid = preco
            return []

        if preco < self.menor_preco_grid:
            self.menor_preco_grid = preco
        if preco > self.maior_preco_grid:
            self.maior_preco_grid = preco

        if self._verificar_stop_loss_grid(preco):
            return []

        if self._verificar_trailing_stop(preco):
            return []

        ordens_executadas = []

        compras_ativas = sum(1 for n in self.niveis_compra if not n['executada'])

        for nivel in self.niveis_compra:
            if preco <= nivel['preco'] and not nivel['executada']:
                if compras_ativas > 0 or len(self.ordens_ativas) < self.max_grids_ativos:

                    custo = nivel['quantidade'] * preco
                    if custo <= self.saldo_usdt:
                        trade = self.executar_compra(
                            preco, nivel['quantidade'], timestamp,
                            tipo_ordem='GRID', nivel=nivel['nivel'],
                            preco_trigger=nivel['preco'])
                        if trade:
                            nivel['executada'] = True
                            nivel['timestamp_execucao'] = timestamp
                            nivel['preco_execucao'] = preco
                            self.ordens_ativas.append(nivel)
                            self.total_compras_grid += 1
                            ordens_executadas.append(trade)
                            self._log(f"Grid COMPRA executada - Nivel {nivel['nivel']}: ${preco:.2f}")

                            if not self.em_posicao:
                                self.em_posicao = True
                                self.preco_entrada_grid = preco

                    compras_ativas -= 1

        for nivel in self.niveis_venda:
            if preco >= nivel['preco'] and not nivel['executada']:
                if self.posicao >= nivel['quantidade']:
                    trade = self.executar_venda(preco, nivel['quantidade'], timestamp,
                                               tipo_ordem='GRID', nivel=nivel['nivel'],
                                               preco_trigger=nivel['preco'])

                    if trade:
                        nivel['executada'] = True
                        nivel['timestamp_execucao'] = timestamp
                        nivel['preco_execucao'] = preco

                        self.ordens_ativas = [o for o in self.ordens_ativas if o['id'] != nivel['id']]
                        self.total_vendas_grid += 1
                        ordens_executadas.append(trade)

                        self._log(f"Grid VENDA executada - Nivel {nivel['nivel']}: ${preco:.2f}")

                        compra_correspondente = None
                        for compra in self.niveis_compra:
                            if compra['executada'] and compra.get('preco_execucao'):
                                if compra['preco_execucao'] < preco:
                                    compra_correspondente = compra
                                    break

                        if compra_correspondente:
                            lucro_ciclo = (preco - compra_correspondente['preco_execucao']) * nivel['quantidade']
                            self.lucro_grid += lucro_ciclo
                            self._log(f"Lucro do ciclo: ${lucro_ciclo:.2f} | Lucro total: ${self.lucro_grid:.2f}")

                        if self.recomprar_apos_venda:
                            self._recompor_grid(preco)

        todas_executadas = all(n['executada'] for n in self.niveis_compra) and \
                          all(n['executada'] for n in self.niveis_venda)

        if todas_executadas and self.recomprar_apos_venda:
            self._log("Todas as ordens executadas, recalculando grid...")
            self.niveis_compra, self.niveis_venda = self._calcular_niveis_grid(preco)

            for nivel in self.niveis_compra:
                nivel['executada'] = False
            for nivel in self.niveis_venda:
                nivel['executada'] = False

            self.ordens_ativas = []
            self._print_configuracao(preco, is_recalc=True)

        return ordens_executadas

    def reset(self):
        super().reset()
        self.grids_calculados = False
        self.niveis_compra = []
        self.niveis_venda = []
        self.ordens_ativas = []
        self.historico_execucoes = []
        self.preco_entrada_grid = None
        self.menor_preco_grid = float('inf')
        self.maior_preco_grid = 0
        self.ultima_recomposicao = None
        self.total_compras_grid = 0
        self.total_vendas_grid = 0
        self.lucro_grid = 0.0

    def get_configuracao(self):
        return {
            'nome': 'Grid Spot (Versão Melhorada)',
            'descricao': 'Cria grades de compra e venda para operar em mercados laterais. Com recompra automática, stop-loss e trailing stop.',
            'parametros': {
                'numero_de_grids': self.num_grids,
                'espacamento_percentual': f"{self.spacing_percent * 100}%",
                'quantidade_por_ordem': f"{self.quantidade_por_ordem} {self.symbol.replace('USDT', '')}",
                'saldo_inicial_usdt': self.saldo_inicial,
                'recomprar_apos_venda': self.recomprar_apos_venda,
                'max_grids_ativos': self.max_grids_ativos,
                'stop_loss_percentual': f"{self.stop_loss_percent * 100}%",
                'usar_trailing_stop': self.usar_trailing_stop,
                'trailing_stop_percentual': f"{self.trailing_stop_percent * 100}%" if self.usar_trailing_stop else 'N/A'
            }
        }

    def get_niveis_grid(self):
        if not self.grids_calculados:
            return None, None

        return {
            'compras': [n for n in self.niveis_compra],
            'vendas': [n for n in self.niveis_venda],
            'executadas': {
                'compras': [n for n in self.niveis_compra if n['executada']],
                'vendas': [n for n in self.niveis_venda if n['executada']]
            },
            'estatisticas': {
                'total_compras': self.total_compras_grid,
                'total_vendas': self.total_vendas_grid,
                'lucro_total': self.lucro_grid,
                'grids_ativos': len(self.ordens_ativas)
            }
        }

    def get_relatorio_estendido(self):
        base_relatorio = self.get_relatorio()

        grid_stats = {
            'grid_total_compras': self.total_compras_grid,
            'grid_total_vendas': self.total_vendas_grid,
            'grid_lucro_total': round(self.lucro_grid, 2),
            'grid_ordens_ativas': len(self.ordens_ativas),
            'grid_preco_entrada': self.preco_entrada_grid,
            'grid_menor_preco': round(self.menor_preco_grid, 2),
            'grid_maior_preco': round(self.maior_preco_grid, 2),
            'grid_amplitude': round(self.maior_preco_grid - self.menor_preco_grid, 2),
            'grid_amplitude_percentual': round((self.maior_preco_grid - self.menor_preco_grid) / self.preco_entrada_grid * 100, 2) if self.preco_entrada_grid else 0
        }

        base_relatorio['grid'] = grid_stats

        return base_relatorio

    def _print_configuracao(self, preco_inicial: float, is_recalc: bool = False):
        msg_type = "RECALCULANDO" if is_recalc else "Configuracao do Grid Spot:"
        print(f"\n{msg_type}")
        print(f"  Preco inicial: ${preco_inicial:.2f}")
        print(f"  Espacamento: {self.spacing_percent * 100}%")

        print(f"  Niveis de compra ({len(self.niveis_compra)}):")
        for nivel in self.niveis_compra[:3]:
            status = "✓" if nivel['executada'] else "○"
            print(f"    [{status}] Nivel {nivel['nivel']}: ${nivel['preco']:.2f}")
        if len(self.niveis_compra) > 3:
            print(f"    ... e mais {len(self.niveis_compra)-3} niveis")

        print(f"  Niveis de venda ({len(self.niveis_venda)}):")
        for nivel in self.niveis_venda[:3]:
            status = "✓" if nivel['executada'] else "○"
            print(f"    [{status}] Nivel {nivel['nivel']}: ${nivel['preco']:.2f}")
        if len(self.niveis_venda) > 3:
            print(f"    ... e mais {len(self.niveis_venda)-3} niveis")

        if self.stop_loss_percent:
            print(f"  Stop-loss: {self.stop_loss_percent * 100}%")
        if self.usar_trailing_stop:
            print(f"  Trailing stop: {self.trailing_stop_percent * 100}%")

        print(f"  Recompra automatica: {'Sim' if self.recomprar_apos_venda else 'Nao'}\n")

    def print_status(self):
        if not self.grids_calculados:
            print("Grid nao inicializado")
            return

        print(f"\n{'='*50}")
        print(f"STATUS DO GRID - {self.symbol}")
        print(f"{'='*50}")
        print(f"Posicao atual: {self.posicao:.8f}")
        print(f"Saldo USDT: ${self.saldo_usdt:.2f}")
        print(f"Preco atual: ${self.ultimo_preco:.2f}")
        print(f"Valor total: ${self.saldo_usdt + self.posicao * self.ultimo_preco:.2f}")
        print(f"\nExecucoes:")
        print(f"  Compras: {self.total_compras_grid}")
        print(f"  Vendas: {self.total_vendas_grid}")
        print(f"  Lucro do grid: ${self.lucro_grid:.2f}")
        print(f"  Ordens ativas: {len(self.ordens_ativas)}")

        if self.ordens_ativas:
            print(f"\nProximos niveis:")
            prox_compra = next((n for n in self.niveis_compra if not n['executada']), None)
            prox_venda = next((n for n in self.niveis_venda if not n['executada']), None)

            if prox_compra:
                print(f"  Proxima compra: ${prox_compra['preco']:.2f} (distancia: {(self.ultimo_preco - prox_compra['preco'])/self.ultimo_preco*100:.2f}%)")
            if prox_venda:
                print(f"  Proxima venda: ${prox_venda['preco']:.2f} (distancia: {(prox_venda['preco'] - self.ultimo_preco)/self.ultimo_preco*100:.2f}%)")

        print(f"{'='*50}\n")
