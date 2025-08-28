#!/usr/bin/env python3
"""
Integração com APIs gratuitas de aviação e voos
"""

import requests
import json
from datetime import datetime
from typing import Optional, Dict, List


class AviationAPIIntegration:
    """Integração com APIs gratuitas de aviação para dados de voos"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; PromoAlertsBot/1.0)'
        })
    
    def get_opensky_flights_to_recife(self) -> List[Dict]:
        """
        API OpenSky Network - TOTALMENTE GRATUITA
        Obter voos em tempo real próximos ao aeroporto de Recife (REC)
        """
        try:
            # Coordenadas aproximadas de Recife
            lat_min, lat_max = -8.5, -7.5
            lon_min, lon_max = -35.5, -34.5
            
            url = "https://opensky-network.org/api/states/all"
            params = {
                'lamin': lat_min,
                'lamax': lat_max, 
                'lomin': lon_min,
                'lomax': lon_max
            }
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            flights = []
            
            if data and 'states' in data and data['states']:
                for state in data['states']:
                    if len(state) >= 11:
                        flight = {
                            'icao24': state[0],
                            'callsign': state[1].strip() if state[1] else 'N/A',
                            'origin_country': state[2],
                            'latitude': state[6],
                            'longitude': state[5], 
                            'altitude': state[7],
                            'velocity': state[9]
                        }
                        flights.append(flight)
                

                return flights
            
        except Exception as e:
            pass
        
        return []
    
    def get_airport_info(self, airport_code: str) -> Optional[Dict]:
        """
        Buscar informações de aeroporto via API pública gratuita
        """
        try:
            # API gratuita de aeroportos
            url = f"https://www.airport-data.com/api/ap_info.json?iata={airport_code}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data:
                return data
            
        except Exception as e:
            pass
        
        return None
    
    def validate_cep(self, cep: str) -> Optional[Dict]:
        """
        Validar CEP usando ViaCEP (API gratuita)
        Útil para validar destinos mencionados em promoções
        """
        try:
            # Limpar CEP (apenas números)
            clean_cep = ''.join(filter(str.isdigit, cep))
            
            if len(clean_cep) != 8:
                return None
            
            url = f"https://viacep.com.br/ws/{clean_cep}/json/"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Verificar se CEP é válido
            if 'erro' not in data:
                return {
                    'cep': data.get('cep'),
                    'cidade': data.get('localidade'),
                    'estado': data.get('uf'),
                    'regiao': self.get_region_by_state(data.get('uf'))
                }
        
        except Exception as e:
            pass
        
        return None
    
    def get_region_by_state(self, state: str) -> str:
        """Mapear estado para região"""
        regions = {
            'AC': 'Norte', 'AL': 'Nordeste', 'AP': 'Norte', 'AM': 'Norte',
            'BA': 'Nordeste', 'CE': 'Nordeste', 'DF': 'Centro-Oeste',
            'ES': 'Sudeste', 'GO': 'Centro-Oeste', 'MA': 'Nordeste',
            'MT': 'Centro-Oeste', 'MS': 'Centro-Oeste', 'MG': 'Sudeste',
            'PA': 'Norte', 'PB': 'Nordeste', 'PR': 'Sul', 'PE': 'Nordeste',
            'PI': 'Nordeste', 'RJ': 'Sudeste', 'RN': 'Nordeste',
            'RS': 'Sul', 'RO': 'Norte', 'RR': 'Norte', 'SC': 'Sul',
            'SP': 'Sudeste', 'SE': 'Nordeste', 'TO': 'Norte'
        }
        return regions.get(state, 'Desconhecida')
    
    def get_ibge_cities_pe(self) -> List[Dict]:
        """
        Obter lista de cidades de Pernambuco via API do IBGE
        Útil para identificar destinos em PE mencionados em promoções
        """
        try:
            # Estado de PE = código 26
            url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/PE/municipios"
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            cities = response.json()
            
            # Simplificar dados
            pe_cities = []
            for city in cities:
                pe_cities.append({
                    'id': city.get('id'),
                    'nome': city.get('nome'),
                    'codigo_ibge': city.get('id')
                })
            
            return pe_cities
        
        except Exception as e:
            pass
        
        return []
    

    
    def enhance_post_with_apis(self, post: Dict) -> Dict:
        """
        Enriquecer post com dados de APIs públicas
        """
        enhanced = post.copy()
        
        # Analisar texto para termos de aviação
        text = f"{post.get('title', '')} {post.get('summary', '')}"
        
        # Buscar por menções a Recife/PE e enriquecer silenciosamente
        if any(term in text.lower() for term in ['recife', 'pernambuco', ' pe ', 'rec']):
            enhanced['aviation_enhanced'] = True
        
        return enhanced
    

