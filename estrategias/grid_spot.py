from .base import EstrategiaBase

class GridSpotStrategy(EstrategiaBase):
    """
    Estrategia Grid Spot.
    
    Funciona melhor em mercados laterais (sideways).
    Cria grades de compra abaixo do preco e venda acima do preco.
    """
    
    def __init__(self, symbol, num_grids=10, spacing_percent=0.01, quantidade_por_ordem=0.001, saldo_inicial=10000):
        super().__init__(symbol, saldo_inicial)
        self.num_grids = num_grids
        self.spacing_percent = spacing_percent
        self.quantidade_por_ordem = quantidade_por_ordem
        
        # Niveis do grid (serao calculados quando o preco inicial for definido)
        self.niveis_compra = []  # Niveis abaixo do preco atual
        self.niveis_venda = []   # Niveis acima do preco atual
        
        # Controle de niveis ja executados
        self.compras_executadas = []
        self.vendas_executadas = []
        
        # Flag para saber se ja calculou os niveis
        self.grids_calculados = False
        
    def calcular_grids(self, preco_inicial):
        """Calcula os niveis do grid baseado no preco inicial"""
        self.niveis_compra = []
        self.niveis_venda = []
        
        # Niveis de compra (abaixo do preco)
        for i in range(1, self.num_grids // 2 + 1):
            preco = preco_inicial * (1 - self.spacing_percent * i)
            self.niveis_compra.append({
                'nivel': i,
                'preco': round(preco, 2),
                'tipo': 'BUY',
                'quantidade': self.quantidade_por_ordem,
                'executada': False
            })
        
        # Niveis de venda (acima do preco)
        for i in range(1, self.num_grids // 2 + 1):
            preco = preco_inicial * (1 + self.spacing_percent * i)
            self.niveis_venda.append({
                'nivel': i,
                'preco': round(preco, 2),
                'tipo': 'SELL',
                'quantidade': self.quantidade_por_ordem,
                'executada': False
            })
        
        # Ordena compras do maior preco para o menor (mais proximo do mercado primeiro)
        self.niveis_compra.sort(key=lambda x: x['preco'], reverse=True)
        self.niveis_venda.sort(key=lambda x: x['preco'])
        
        self.grids_calculados = True
        
        # Limpa registros anteriores
        self.compras_executadas = []
        self.vendas_executadas = []
        
    def processar_preco(self, preco, timestamp):
        """Processa cada preco e verifica se algum nivel do grid foi atingido"""
        self.ultimo_preco = preco
        
        # Primeira execucao: calcula grids baseado no primeiro preco
        if not self.grids_calculados:
            self.calcular_grids(preco)
            self._print_configuracao(preco)
            return []
        
        ordens_executadas = []
        
        # Verifica niveis de compra
        for nivel in self.niveis_compra:
            if preco <= nivel['preco'] and not nivel['executada']:
                # Executa compra
                trade = self.executar_compra(preco, nivel['quantidade'], nivel=nivel['nivel'], preco_trigger=nivel['preco'])
                if trade:
                    nivel['executada'] = True
                    self.compras_executadas.append(nivel)
                    ordens_executadas.append(trade)
        
        # Verifica niveis de venda
        for nivel in self.niveis_venda:
            if preco >= nivel['preco'] and not nivel['executada']:
                # Executa venda
                trade = self.executar_venda(preco, nivel['quantidade'], nivel=nivel['nivel'], preco_trigger=nivel['preco'])
                if trade:
                    nivel['executada'] = True
                    self.vendas_executadas.append(nivel)
                    ordens_executadas.append(trade)
        
        return ordens_executadas
    
    def reset(self):
        """Reseta a estrategia para uma nova simulacao"""
        super().reset()
        self.grids_calculados = False
        self.niveis_compra = []
        self.niveis_venda = []
        self.compras_executadas = []
        self.vendas_executadas = []
    
    def get_configuracao(self):
        return {
            'nome': 'Grid Spot',
            'descricao': 'Cria grades de compra e venda para operar em mercados laterais',
            'parametros': {
                'numero_de_grids': self.num_grids,
                'espacamento_percentual': f"{self.spacing_percent * 100}%",
                'quantidade_por_ordem': self.quantidade_por_ordem,
                'saldo_inicial_usdt': self.saldo_inicial
            }
        }
    
    def get_niveis_grid(self):
        """Retorna os niveis do grid para visualizacao"""
        if not self.grids_calculados:
            return None, None
        return self.niveis_compra, self.niveis_venda
    
    def _print_configuracao(self, preco_inicial):
        """Printa a configuracao do grid"""
        print(f"\nConfiguracao do Grid Spot:")
        print(f"  Niveis de compra ({len(self.niveis_compra)}):")
        for nivel in self.niveis_compra[:3]:
            print(f"    Nivel {nivel['nivel']}: ${nivel['preco']}")
        if len(self.niveis_compra) > 3:
            print(f"    ... e mais {len(self.niveis_compra)-3} niveis")
        
        print(f"  Niveis de venda ({len(self.niveis_venda)}):")
        for nivel in self.niveis_venda[:3]:
            print(f"    Nivel {nivel['nivel']}: ${nivel['preco']}")
        if len(self.niveis_venda) > 3:
            print(f"    ... e mais {len(self.niveis_venda)-3} niveis")