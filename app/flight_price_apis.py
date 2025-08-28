#!/usr/bin/env python3
"""
Flight Price APIs for SP → Recife
APIs focadas em PREÇOS de passagens e MILHAS para GitHub Actions
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
import time

class FlightPriceChecker:
    """APIs especializadas em preços de passagens SP → Recife"""
    
    def __init__(self):
        # Chaves API (definir como GitHub Secrets)
        self.amadeus_key = os.getenv('AMADEUS_API_KEY')
        self.amadeus_secret = os.getenv('AMADEUS_API_SECRET')

        self.opensky_client_id = os.getenv('OPENSKY_CLIENT_ID')
        self.opensky_client_secret = os.getenv('OPENSKY_CLIENT_SECRET')
        self.amadeus_token = None
        
        # Configurações específicas SP → Recife
        self.origins = ['GRU', 'CGH']  # Guarulhos e Congonhas
        self.destination = 'REC'  # Recife
        
    def get_amadeus_token(self) -> Optional[str]:
        """Obter token Amadeus (2000 requests/mês GRÁTIS)"""
        if not self.amadeus_key or not self.amadeus_secret:
            return None
            
        try:
            url = "https://test.api.amadeus.com/v1/security/oauth2/token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.amadeus_key,
                'client_secret': self.amadeus_secret
            }
            
            print(f"🔑 Solicitando token Amadeus...")
            response = requests.post(url, data=data, timeout=10)
            print(f"📡 Status Code: {response.status_code}")
            
            response.raise_for_status()
            
            token_data = response.json()
            print(f"📄 Response keys: {list(token_data.keys())}")
            
            self.amadeus_token = token_data['access_token']
            print(f"✅ Token Amadeus obtido com sucesso")
            return self.amadeus_token
            
        except Exception as e:
            print(f"❌ Erro token Amadeus: {e}")
            if 'response' in locals():
                print(f"📄 Response content: {response.text}")
            return None
    
    def get_sp_recife_prices(self, departure_date: str = None) -> Dict:
        """
        FOCO: Preços atuais SP → Recife via Amadeus
        Retorna apenas os preços mais baratos encontrados
        """
        if not departure_date:
            # Próxima segunda-feira (quando geralmente há mais voos)
            today = datetime.now()
            days_ahead = 7 - today.weekday()  # Segunda = 0
            if days_ahead <= 0:
                days_ahead += 7
            departure_date = (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        if not self.amadeus_token:
            if not self.get_amadeus_token():
                return {'error': 'Token não disponível'}
        
        try:
            url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
            headers = {'Authorization': f'Bearer {self.amadeus_token}'}
            
            all_prices = []
            
            # Buscar de ambos aeroportos SP
            for origin in self.origins:
                params = {
                    'originLocationCode': origin,
                    'destinationLocationCode': self.destination,
                    'departureDate': departure_date,
                    'adults': 1,
                    'currencyCode': 'BRL',
                    'max': 10
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=15)
                response.raise_for_status()
                
                data = response.json()
                if 'data' in data and data['data']:
                    for flight in data['data']:
                        price_info = self._extract_price_info(flight, origin)
                        if price_info:
                            all_prices.append(price_info)
            
            if not all_prices:
                return {'error': 'Nenhum voo encontrado'}
            
            # Ordenar por preço e retornar apenas os dados essenciais
            all_prices.sort(key=lambda x: x['price'])
            cheapest = all_prices[0]
            
            return {
                'route': 'SP → REC',
                'date': departure_date,
                'cheapest_price': cheapest['price'],
                'cheapest_origin': cheapest['origin'],
                'airline': cheapest['airline'],
                'departure_time': cheapest['departure_time'],
                'price_range': {
                    'min': min(p['price'] for p in all_prices),
                    'max': max(p['price'] for p in all_prices),
                    'avg': round(sum(p['price'] for p in all_prices) / len(all_prices), 2)
                },
                'flights_found': len(all_prices),
                'timestamp': datetime.now().isoformat(),
                'source': 'Amadeus'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_opensky_recife_traffic(self) -> Dict:
        """
        Tráfego aéreo na região de Recife usando conta OpenSky (4000 requests grátis)
        """
        try:
            url = "https://opensky-network.org/api/states/all"
            params = {
                'lamin': -8.5,   # Região de Recife
                'lamax': -7.5,
                'lomin': -35.5, 
                'lomax': -34.5
            }
            
            # Usar autenticação com Client ID se disponível (4000 créditos)
            headers = {}
            auth_method = "sem autenticação"
            
            if self.opensky_client_id:
                # OpenSky usa Basic Auth com Client ID como username
                auth = (self.opensky_client_id, self.opensky_client_secret or '')
                auth_method = f"Client ID: {self.opensky_client_id} (4000 créditos)"
                print(f"🔐 Usando OpenSky com {auth_method}")
            else:
                auth = None
                print("🌐 Usando OpenSky sem autenticação (ilimitado mas menos dados)")
            
            response = requests.get(url, params=params, auth=auth, headers=headers, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            aircraft_count = len(data['states']) if data['states'] else 0
            
            # Analisar voos para Recife especificamente
            flights_to_rec = []
            sp_airports = ['GRU', 'CGH', 'VCP']  # São Paulo airports
            
            if data['states']:
                for state in data['states']:
                    if state[1]:  # Tem callsign
                        callsign = state[1].strip()
                        # Tentar identificar voos comerciais para Recife
                        if any(airline in callsign for airline in ['GLO', 'AZU', 'TAM', 'ONE']):
                            flights_to_rec.append({
                                'callsign': callsign,
                                'origin_country': state[2],
                                'altitude': state[7],
                                'velocity': state[9],
                                'heading': state[10],
                                'lat': state[6],
                                'lon': state[5]
                            })
            
            return {
                'source': f'OpenSky ({auth_method})',
                'client_id': self.opensky_client_id if self.opensky_client_id else 'anonymous',
                'aircraft_in_region': aircraft_count,
                'commercial_flights_detected': len(flights_to_rec),
                'sample_flights': flights_to_rec[:3],  # Top 3
                'air_traffic_level': self._assess_traffic_level(aircraft_count),
                'timestamp': datetime.now().isoformat(),
                'api_status': 'success'
            }
            
        except Exception as e:
            return {'error': str(e), 'source': 'OpenSky'}
    
    def _assess_traffic_level(self, aircraft_count: int) -> str:
        """Avaliar nível de tráfego aéreo"""
        if aircraft_count >= 15:
            return 'ALTO'
        elif aircraft_count >= 8:
            return 'MÉDIO'
        elif aircraft_count >= 3:
            return 'BAIXO'
        else:
            return 'MUITO_BAIXO'
    
    def _extract_price_info(self, flight_data: Dict, origin: str) -> Optional[Dict]:
        """Extrair apenas info essencial de preço"""
        try:
            price = float(flight_data['price']['total'])
            
            # Primeiro segmento
            segment = flight_data['itineraries'][0]['segments'][0]
            departure_time = segment['departure']['at']
            carrier = segment['carrierCode']
            
            return {
                'price': price,
                'origin': origin,
                'airline': carrier,
                'departure_time': departure_time,
                'stops': len(flight_data['itineraries'][0]['segments']) - 1
            }
        except:
            return None
    
    def estimate_miles_prices(self, cash_price: float) -> Dict:
        """
        Estimativa de preços em milhas baseada em preços em dinheiro
        Usando taxas médias dos programas brasileiros
        """
        # Taxas aproximadas dos programas (milhas por R$)
        miles_programs = {
            'Smiles (GOL)': {
                'rate': 0.025,  # ~25 milhas por R$1
                'min_miles': 15000,  # Mínimo doméstico
                'fees': 120  # Taxa média
            },
            'TudoAzul (Azul)': {
                'rate': 0.022,  # ~22 milhas por R$1  
                'min_miles': 12000,
                'fees': 140
            },
            'LATAM Pass': {
                'rate': 0.020,  # ~20 milhas por R$1
                'min_miles': 17000,
                'fees': 100
            },
            'Livelo': {
                'rate': 0.030,  # ~30 pontos por R$1
                'min_miles': 20000,
                'fees': 80
            }
        }
        
        estimates = {}
        
        for program, config in miles_programs.items():
            estimated_miles = max(
                int(cash_price * config['rate'] * 1000),  # Converter para milhas
                config['min_miles']
            )
            
            estimates[program] = {
                'estimated_miles': estimated_miles,
                'fees_brl': config['fees'],
                'total_cost_brl': config['fees'],  # Apenas taxas se usar milhas
                'savings_vs_cash': cash_price - config['fees'],
                'worth_using_miles': (cash_price - config['fees']) > 50  # Vale a pena se economizar mais de R$50
            }
        
        return {
            'cash_price_reference': cash_price,
            'programs': estimates,
            'best_miles_option': min(estimates.keys(), 
                                   key=lambda x: estimates[x]['estimated_miles']),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_historical_price_trend(self) -> Dict:
        """
        Simular tendência de preços usando dados atuais
        Útil para avaliar se um preço é uma boa oferta
        """
        try:
            current_prices = self.get_sp_recife_prices()
            
            if 'error' in current_prices:
                return current_prices
            
            current_price = current_prices['cheapest_price']
            
            # Faixas de preços típicas SP → Recife (baseado em dados históricos)
            price_ranges = {
                'excelente': 300,    # Abaixo de R$300 = excelente
                'boa': 450,          # R$300-450 = boa oferta  
                'regular': 600,      # R$450-600 = regular
                'cara': 800          # Acima de R$600 = cara
            }
            
            # Avaliar o preço atual
            if current_price <= price_ranges['excelente']:
                rating = 'EXCELENTE'
                savings = price_ranges['regular'] - current_price
            elif current_price <= price_ranges['boa']:
                rating = 'BOA'
                savings = price_ranges['regular'] - current_price
            elif current_price <= price_ranges['regular']:
                rating = 'REGULAR'
                savings = 0
            else:
                rating = 'CARA'
                savings = 0
            
            return {
                'current_price': current_price,
                'price_rating': rating,
                'potential_savings': savings,
                'price_ranges': price_ranges,
                'recommendation': self._get_price_recommendation(rating, current_price),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_price_recommendation(self, rating: str, price: float) -> str:
        """Recomendação baseada no preço"""
        if rating == 'EXCELENTE':
            return f"🔥 COMPRE AGORA! Preço excelente de R${price:.0f}"
        elif rating == 'BOA':
            return f"✅ Boa oferta por R${price:.0f}. Recomendado!"
        elif rating == 'REGULAR':
            return f"⚠️ Preço regular R${price:.0f}. Aguarde melhor oferta."
        else:
            return f"❌ Preço alto R${price:.0f}. Evite comprar agora."
    
    def get_complete_sp_recife_analysis(self, departure_date: str = None) -> Dict:
        """
        Análise completa: preços em dinheiro + estimativas de milhas
        Otimizado para GitHub Actions (rápido e focado)
        """
        print("🔍 Analisando preços SP → Recife...")
        
        # 1. Preços atuais
        price_data = self.get_sp_recife_prices(departure_date)
        
        if 'error' in price_data:
            return {
                'error': price_data['error'],
                'timestamp': datetime.now().isoformat()
            }
        
        # 2. Estimativas de milhas
        cash_price = price_data['cheapest_price']
        miles_estimates = self.estimate_miles_prices(cash_price)
        
        # 3. Análise de tendência
        trend_analysis = self.get_historical_price_trend()
        
        # 4. Dados de tráfego aéreo (OpenSky)
        air_traffic = self.get_opensky_recife_traffic()
        
        # 5. Resultado consolidado
        result = {
            'summary': {
                'route': 'São Paulo → Recife',
                'cheapest_price_brl': cash_price,
                'best_origin': price_data['cheapest_origin'],
                'airline': price_data['airline'],
                'price_rating': trend_analysis.get('price_rating', 'UNKNOWN'),
                'recommendation': trend_analysis.get('recommendation', 'Dados insuficientes')
            },
            'cash_prices': price_data,
            'miles_estimates': miles_estimates,
            'trend_analysis': trend_analysis,
            'air_traffic': air_traffic,
            'api_usage': {
                'amadeus_requests': 2,  # GRU + CGH
                'opensky_requests': 1,
                'total_cost': 0.00,
                'remaining_free_requests': {
                    'amadeus': '~1998/2000',
                    'opensky': '~3999/4000 créditos' if self.opensky_client_id else 'unlimited'
                }
            },
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"✅ Análise concluída: R${cash_price:.0f} ({trend_analysis.get('price_rating', 'N/A')})")
        
        return result
    
    def format_for_github_actions(self, analysis: Dict) -> str:
        """
        Formatar resultado para GitHub Actions output
        Retorna string concisa para usar em workflows
        """
        if 'error' in analysis:
            return f"ERROR: {analysis['error']}"
        
        summary = analysis['summary']
        best_miles = analysis['miles_estimates']['best_miles_option']
        best_miles_data = analysis['miles_estimates']['programs'][best_miles]
        
        return (
            f"SP→REC: R${summary['cheapest_price_brl']:.0f} "
            f"({summary['price_rating']}) | "
            f"Melhor milhas: {best_miles} "
            f"({best_miles_data['estimated_miles']:,} milhas + R${best_miles_data['fees_brl']})"
        )


def main():
    """Função principal para GitHub Actions"""
    print("🎯 Flight Price Checker - SP → Recife")
    print("=" * 50)
    
    checker = FlightPriceChecker()
    
    # Análise completa
    analysis = checker.get_complete_sp_recife_analysis()
    
    if 'error' in analysis:
        print(f"❌ Erro: {analysis['error']}")
        return
    
    # Mostrar resultado resumido
    summary = analysis['summary']
    print(f"\n🎯 RESULTADO:")
    print(f"   💰 Preço mais barato: R$ {summary['cheapest_price_brl']:.2f}")
    print(f"   ✈️  Melhor origem: {summary['best_origin']}")
    print(f"   🏢 Companhia: {summary['airline']}")
    print(f"   📊 Avaliação: {summary['price_rating']}")
    print(f"   💡 {summary['recommendation']}")
    
    # Milhas
    miles = analysis['miles_estimates']
    best_program = miles['best_miles_option']
    best_data = miles['programs'][best_program]
    print(f"\n💳 MELHOR OPÇÃO EM MILHAS:")
    print(f"   🎫 Programa: {best_program}")
    print(f"   ✈️  Milhas necessárias: {best_data['estimated_miles']:,}")
    print(f"   💰 Taxas: R$ {best_data['fees_brl']}")
    print(f"   💡 Vale a pena? {'SIM' if best_data['worth_using_miles'] else 'NÃO'}")
    
    # Output para GitHub Actions
    github_output = checker.format_for_github_actions(analysis)
    print(f"\n🤖 GitHub Actions Output:")
    print(f"   {github_output}")
    
    # Salvar resultado completo
    with open('flight_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Análise salva em flight_analysis.json")


if __name__ == "__main__":
    main()
