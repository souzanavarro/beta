import streamlit as st
import pandas as pd
import requests
import openpyxl
from pedidos import obter_coordenadas
from database import salvar_cnpj_enderecos, carregar_cnpj_enderecos, limpar_cnpj_enderecos
import io
import time
import json
import logging
import re # Importado para limpeza de CNPJ

# Configuração básica do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extrair_nome_campo(valor, chave_nome='nome', chave_sigla='sigla'):
    """Extrai o nome de um campo que pode ser um dict ou string."""
    if isinstance(valor, dict):
        return valor.get(chave_nome, valor.get(chave_sigla, ''))
    return str(valor) if valor else ''

def formatar_telefone(ddd, numero):
    """Formata DDD e número em um telefone limpo."""
    ddd_str = str(ddd).strip() if ddd else ''
    num_str = str(numero).strip() if numero else ''
    if not ddd_str and not num_str:
        return None
    # Remove caracteres não numéricos
    tel_limpo = re.sub(r'\D', '', ddd_str + num_str)
    return tel_limpo if tel_limpo else None

def formatar_cep(cep):
    """Formata um CEP removendo caracteres não numéricos e adicionando hífen."""
    if not cep:
        return None
    cep_limpo = re.sub(r'\\D', '', str(cep))
    if len(cep_limpo) == 8:
        # Corrigido: Adicionada a aspa dupla final na f-string
        return f"{cep_limpo[:5]}-{cep_limpo[5:]}"
    return cep_limpo # Retorna limpo se não tiver 8 dígitos

def buscar_endereco_cnpj(cnpj):
    """Busca dados de um CNPJ em várias APIs.

    Retorna um dicionário com:
    'logradouro', 'numero', 'complemento', 'bairro', 'municipio', 'uf', 'cep',
    'situacao', 'telefone', 'email', 'nome_empresarial', 'ocorrencia_fiscal', 'regime_apuracao',
    'suframa_ativo', 'numero_inscricao_suframa'.
    Retorna None para campos não encontrados.
    """
    cnpj_limpo = re.sub(r'\\D', '', str(cnpj))
    if len(cnpj_limpo) != 14:
        logging.warning(f"CNPJ inválido fornecido: {cnpj}")
        # Retorna a estrutura esperada com None
        return {
            'logradouro': None, 'numero': None, 'complemento': None, 'bairro': None,
            'municipio': None, 'uf': None, 'cep': None, 'situacao': 'Inválido',
            'telefone': None, 'email': None, 'nome_empresarial': None,
            'ocorrencia_fiscal': None, 'regime_apuracao': None,
            'suframa_ativo': None,
            'numero_inscricao_suframa': None # Novo campo
        }

    apis = [
        {
            "nome": "BrasilAPI",
            "url": f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
            "parser": lambda data: {
                "logradouro": data.get('logradouro'),
                "numero": data.get('numero'),
                "complemento": data.get('complemento'),
                "bairro": data.get('bairro'),
                "municipio": extrair_nome_campo(data.get('municipio')),
                "uf": extrair_nome_campo(data.get('uf'), chave_nome='sigla', chave_sigla='sigla'),
                "cep": formatar_cep(data.get('cep')),
                "situacao": data.get('situacao_cadastral') or data.get('situacao'),
                "telefone": formatar_telefone(data.get('ddd_telefone_1'), data.get('telefone_1')),
                "email": data.get('email'),
                "nome_empresarial": data.get('razao_social'),
                "ocorrencia_fiscal": data.get('descricao_situacao_cadastral'), # Ou outro campo relevante
                "regime_apuracao": data.get('opcao_pelo_simples'), # Exemplo, pode variar
                "suframa_ativo": data.get('inscricao_suframa'), # Campo hipotético para status
                "numero_inscricao_suframa": data.get('inscricao_suframa') # Campo hipotético para número
            }
        },
        {
            "nome": "CNPJ.ws",
            "url": f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}",
            "parser": lambda data: {
                "logradouro": data.get('estabelecimento', {}).get('logradouro'),
                "numero": data.get('estabelecimento', {}).get('numero'),
                "complemento": data.get('estabelecimento', {}).get('complemento'),
                "bairro": data.get('estabelecimento', {}).get('bairro'),
                "municipio": extrair_nome_campo(data.get('estabelecimento', {}).get('cidade')),
                "uf": extrair_nome_campo(data.get('estabelecimento', {}).get('estado'), chave_nome='sigla', chave_sigla='sigla'),
                "cep": formatar_cep(data.get('estabelecimento', {}).get('cep')),
                "situacao": data.get('estabelecimento', {}).get('situacao_cadastral') or data.get('estabelecimento', {}).get('situacao'),
                "telefone": formatar_telefone(data.get('estabelecimento', {}).get('ddd1'), data.get('estabelecimento', {}).get('telefone1')),
                "email": data.get('estabelecimento', {}).get('email'),
                "nome_empresarial": data.get('razao_social'),
                "ocorrencia_fiscal": data.get('estabelecimento', {}).get('situacao_especial', {}).get('nome'), # Exemplo
                "regime_apuracao": data.get('simples', {}).get('simples'), # Exemplo
                # Tenta pegar status e número da mesma fonte, se disponível
                "suframa_ativo": data.get('estabelecimento', {}).get('inscricoes_estaduais', [{}])[0].get('inscricao_suframa_status'), # Hipotético,
                "numero_inscricao_suframa": data.get('estabelecimento', {}).get('inscricoes_estaduais', [{}])[0].get('inscricao_suframa') # Hipotético
            }
        },
        {
            "nome": "ReceitaWS",
            "url": f"https://www.receitaws.com.br/v1/cnpj/{cnpj_limpo}",
            "parser": lambda data: {
                "logradouro": data.get('logradouro'),
                "numero": data.get('numero'),
                "complemento": data.get('complemento'),
                "bairro": data.get('bairro'),
                "municipio": extrair_nome_campo(data.get('municipio')),
                "uf": extrair_nome_campo(data.get('uf'), chave_nome='sigla', chave_sigla='sigla'),
                "cep": formatar_cep(data.get('cep')),
                "situacao": data.get('situacao'),
                "telefone": formatar_telefone('', data.get('telefone')), # ReceitaWS pode ter DDD junto
                "email": data.get('email'),
                "nome_empresarial": data.get('nome'), # ReceitaWS usa 'nome' para razão social
                "ocorrencia_fiscal": data.get('motivo_situacao'), # Exemplo
                "regime_apuracao": data.get('opcao_pelo_simples'), # Exemplo
                "suframa_ativo": data.get('inscricao_suframa'), # Campo hipotético para status
                "numero_inscricao_suframa": data.get('inscricao_suframa') # Campo hipotético para número
            }
        },
    ]

    # Inicializa com None para garantir que todas as chaves existam
    resultado = {
        'logradouro': None, 'numero': None, 'complemento': None, 'bairro': None,
        'municipio': None, 'uf': None, 'cep': None, 'situacao': None,
        'telefone': None, 'email': None, 'nome_empresarial': None,
        'ocorrencia_fiscal': None, 'regime_apuracao': None,
        'suframa_ativo': None,
        'numero_inscricao_suframa': None # Novo campo
    }

    for api in apis:
        logging.info(f"Tentando API {api['nome']} para CNPJ {cnpj_limpo}")
        try:
            resp = requests.get(api["url"], timeout=10)
            resp.raise_for_status()

            data = resp.json()
            if not data:
                 logging.warning(f"API {api['nome']} retornou dados vazios para CNPJ {cnpj_limpo}")
                 continue

            dados_api = api["parser"](data)

            # Preenche os campos do resultado APENAS se ainda não estiverem preenchidos
            for key in resultado.keys():
                if not resultado[key] and dados_api.get(key):
                    valor = str(dados_api[key]).strip()
                    if valor and valor.lower() != 'none': # Evita preencher com "None" literal
                        resultado[key] = valor
                        if resultado[key]: # Log apenas se encontrou algo útil
                            logging.info(f"Campo '{key}' encontrado para CNPJ {cnpj_limpo} via {api['nome']}")

        except requests.exceptions.Timeout:
            logging.warning(f"Timeout ao consultar API {api['nome']} para CNPJ {cnpj_limpo}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                 logging.info(f"CNPJ {cnpj_limpo} não encontrado na API {api['nome']} (404)")
            elif e.response.status_code == 429:
                 logging.warning(f"Limite de taxa atingido na API {api['nome']} para CNPJ {cnpj_limpo} (429)")
                 time.sleep(1) # Pausa antes de tentar a próxima
            else:
                 logging.error(f"Erro HTTP {e.response.status_code} ao consultar API {api['nome']} para CNPJ {cnpj_limpo}: {e}")
        except json.JSONDecodeError:
            response_text = ""
            try:
                response_text = resp.text
            except Exception:
                response_text = "[Não foi possível ler o texto da resposta]"
            logging.error(f"Erro ao decodificar JSON da API {api['nome']} para CNPJ {cnpj_limpo}. Resposta: {response_text[:200]}...")
        except Exception as e:
            logging.error(f"Erro inesperado ao consultar API {api['nome']} para CNPJ {cnpj_limpo}: {e}", exc_info=True)
        finally:
            time.sleep(0.2) # Pequena pausa entre APIs

    # Validação final: Se não encontrou logradouro ou município, considera endereço inválido
    if not resultado['logradouro'] and not resultado['municipio']:
        if resultado['situacao'] != 'Inválido':
            logging.warning(f"Nenhuma API encontrou dados de endereço suficientes para CNPJ {cnpj_limpo}")
        # Mantém os outros campos que podem ter sido encontrados (situação, tel, email)

    return resultado

def construir_endereco_completo(dados):
    """Constrói a string de endereço completo a partir dos componentes."""
    partes = [
        dados.get('logradouro'),
        dados.get('numero'),
        dados.get('complemento'),
        dados.get('bairro'),
        dados.get('municipio'),
        dados.get('uf'),
        # dados.get('cep') # Opcional incluir CEP na string
    ]
    # Filtra partes vazias ou None e junta com vírgula
    endereco = ', '.join(filter(None, [str(p).strip() for p in partes if p]))
    return endereco if endereco else None


def google_maps_link(endereco_completo=None, dados_endereco=None):
    """Gera link do Google Maps a partir de uma string de endereço ou componentes."""
    query = None
    if dados_endereco:
        # Tenta construir a query a partir dos componentes para maior precisão
        partes_query = [
            dados_endereco.get('logradouro'),
            dados_endereco.get('numero'),
            dados_endereco.get('bairro'),
            dados_endereco.get('municipio'), # Corrigido: Adicionado ')'
            dados_endereco.get('uf'),        # Corrigido: Adicionado ')'
            dados_endereco.get('cep')         # Corrigido: Adicionado ')'
        ]
        # Filtra partes vazias e junta com vírgula
        query = ', '.join(filter(None, [str(p).strip() for p in partes_query if p]))
    elif endereco_completo:
        query = str(endereco_completo).strip()

    if not query or query.lower() in ["não encontrado", "cnpj inválido", "", ","] or len(re.sub(r'[,\\s]', '', query)) <= 5:
        return ""
    try:
        return f"https://www.google.com/maps/search/?api=1&query={requests.utils.quote(query)}"
    except Exception:
        return ""

def buscar_cnpj_no_banco(cnpj):
    """Busca um CNPJ específico no banco de dados local."""
    df_banco = carregar_cnpj_enderecos()
    if df_banco.empty:
        return None

    # Padroniza nomes das colunas para busca (case-insensitive)
    df_banco.columns = [str(col).strip().lower() for col in df_banco.columns]

    if 'cnpj' not in df_banco.columns:
        logging.error("Coluna 'cnpj' não encontrada no DataFrame carregado do banco.")
        return None

    # Limpa CNPJ da busca e do DataFrame
    cnpj_limpo = re.sub(r'\D', '', str(cnpj)).zfill(14)
    try:
        # Tenta converter para string antes de aplicar regex
        df_banco['cnpj'] = df_banco['cnpj'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(14)
    except Exception as e:
        logging.error(f"Erro ao limpar coluna CNPJ do banco: {e}")
        return None # Retorna None se houver erro na limpeza

    resultado = df_banco[df_banco['cnpj'] == cnpj_limpo]
    if not resultado.empty:
        # Retorna a primeira linha encontrada como um dicionário
        # Renomeia colunas para o padrão esperado (primeira letra maiúscula)
        row_dict = resultado.iloc[0].to_dict()
        standardized_dict = {
            'CNPJ': row_dict.get('cnpj'),
            'Status': row_dict.get('status'),
            'Cód. Edata': row_dict.get('cód. edata', row_dict.get('cod. edata', row_dict.get('cod_edata'))),
            'Cód. Mega': row_dict.get('cód. mega', row_dict.get('cod. mega', row_dict.get('cod_mega'))),
            'Nome': row_dict.get('nome'),
            'Endereco': row_dict.get('endereco'),
            'Telefone': row_dict.get('telefone'),
            'Email': row_dict.get('email'),
            'Latitude': row_dict.get('latitude'),
            'Longitude': row_dict.get('longitude'),
            'Google Maps': row_dict.get('google maps', row_dict.get('googlemaps', row_dict.get('maps'))),
            # Adiciona os novos campos SUFRAMA
            'Suframa Ativo': row_dict.get('suframa ativo', row_dict.get('suframa_ativo')),
            'Numero Inscricao Suframa': row_dict.get('numero inscricao suframa', row_dict.get('numero_inscricao_suframa'))
        }
        # Adiciona quaisquer outras colunas que não foram padronizadas
        outras_chaves = {k.capitalize(): v for k, v in row_dict.items() if k not in standardized_dict and k not in [
            'cnpj', 'status', 'cód. edata', 'cod. edata', 'cod_edata', 'cód. mega', 'cod. mega', 'cod_mega', 'nome', 'endereco', 'telefone', 'email', 'latitude', 'longitude', 'google maps', 'googlemaps', 'maps',
            'suframa ativo', 'suframa_ativo', 'numero inscricao suframa', 'numero_inscricao_suframa'
            ]}
        standardized_dict.update(outras_chaves)
        return standardized_dict
    return None

def situacao_cadastral_str(situacao):
    """Retorna a string descritiva da situação cadastral, mapeando códigos conhecidos."""
    if pd.isna(situacao) or situacao is None:
        return "Não informada"

    situacao_str = str(situacao).strip()

    # Mapeamento de códigos comuns (baseado na Receita Federal/BrasilAPI)
    mapeamento = {
        "01": "NULA",
        "1": "NULA",
        "02": "ATIVA",
        "2": "ATIVA",
        "03": "SUSPENSA",
        "3": "SUSPENSA",
        "04": "INAPTA",
        "4": "INAPTA",
        "08": "BAIXADA",
        "8": "BAIXADA"
    }

    # Retorna a descrição mapeada se for um código conhecido
    if situacao_str in mapeamento:
        return mapeamento[situacao_str]

    # Se já for uma descrição (ex: "ATIVA"), retorna ela mesma
    # (Verifica se não é puramente numérico para evitar confundir com códigos desconhecidos)
    if not situacao_str.isdigit():
        return situacao_str.capitalize() # Capitaliza para consistência

    # Se for um número não mapeado ou string vazia, retorna como estava ou "Desconhecida"
    return situacao_str if situacao_str else "Não informada"

def regime_apuracao_str(valor):
    """Converte o valor do regime de apuração (Simples Nacional) para uma string descritiva."""
    if pd.isna(valor) or valor is None:
        return "Não informado"

    valor_str = str(valor).strip().lower()

    if valor_str in ['true', 'sim', 's']:
        return "Optante pelo Simples"
    elif valor_str in ['false', 'nao', 'n']:
        return "Não Optante pelo Simples"
    elif valor_str: # Se for outra string não vazia (ex: "MEI")
        return valor_str.capitalize()
    else:
        return "Não informado"

def suframa_status_str(valor):
    """Converte o valor do status SUFRAMA para uma string descritiva."""
    if pd.isna(valor) or valor is None:
        return "Não informado"

    valor_str = str(valor).strip().lower()

    # Adapte estas condições se descobrir os valores reais retornados pelas APIs
    if valor_str in ['ativo', 'ativa', 'true', 'sim', 's']:
        return "Ativo"
    elif valor_str in ['inativo', 'inativa', 'false', 'nao', 'n', 'baixado', 'baixada']:
        return "Inativo/Baixado"
    elif valor_str:
        return f"Informado: {valor_str.capitalize()}" # Mostra o que foi encontrado
    else:
        return "Não informado"

def show():
    if 'processing_cnpj' not in st.session_state:
        st.session_state.processing_cnpj = False

    st.title("📑 Busca de Dados por CNPJ")
    st.markdown("Busque endereços, coordenadas, situação, telefones e emails a partir de CNPJs.")

    # --- Busca em lote ---
    with st.container(border=True):
        st.subheader("📤 Busca em Lote")
        st.write("Faça upload de uma planilha (.xlsx, .xls, .csv) com uma coluna chamada 'CNPJ'.")
        arquivo = st.file_uploader("Upload da planilha", type=["xlsx", "xls", "csv"], key="upload_lote")

        processar_lote = st.button(
            "⚙️ Processar Planilha",
            key="btn_buscar_lote",
            disabled=st.session_state.processing_cnpj or arquivo is None,
            help="Busca dados para todos os CNPJs da planilha, priorizando o banco local."
        )

        if processar_lote and arquivo:
            st.session_state.processing_cnpj = True
            st.rerun()

        if st.session_state.processing_cnpj and arquivo:
            try:
                if arquivo.name.endswith(".csv"):
                    df = pd.read_csv(arquivo, dtype=str, keep_default_na=False)
                else:
                    df = pd.read_excel(arquivo, dtype=str)

                # Encontra coluna CNPJ (case-insensitive e strip)
                cnpj_col = next((col for col in df.columns if str(col).strip().lower() == 'cnpj'), None)
                if not cnpj_col:
                    st.error("Coluna 'CNPJ' não encontrada. Verifique o nome da coluna.")
                    st.session_state.processing_cnpj = False
                    st.stop()

                # Renomeia para 'CNPJ' padrão, limpa e remove duplicados
                df = df.rename(columns={cnpj_col: "CNPJ"})
                # Padroniza CNPJ: remove tudo que não for número e preenche com zeros à esquerda
                df["CNPJ"] = df["CNPJ"].astype(str).str.replace(r'\D', '', regex=True).str.zfill(14)
                df = df.drop_duplicates(subset=["CNPJ"])
                df = df[df["CNPJ"].str.len() == 14] # Garante que só CNPJs válidos prossigam
                total_cnpjs = len(df)

                if total_cnpjs == 0:
                    st.warning("Nenhum CNPJ válido encontrado na planilha após limpeza.")
                    st.session_state.processing_cnpj = False
                    st.stop()

                st.info(f"Iniciando processamento de {total_cnpjs} CNPJs únicos e válidos...")

                resultados = []
                progress = st.progress(0)
                status_text = st.empty()
                cnpjs_processados = 0

                for idx, row in df.iterrows():
                    cnpj = row["CNPJ"]
                    status_text.text(f"Processando {cnpjs_processados + 1}/{total_cnpjs}: {cnpj}")

                    # 1. Buscar no banco
                    row_banco = buscar_cnpj_no_banco(cnpj)
                    dados_finais = {
                        'CNPJ': cnpj,
                        'Endereco': None, 'Status': None, 'Telefone': None, 'Email': None,
                        'Latitude': None, 'Longitude': None, 'Google Maps': None
                    }
                    # Mantém outras colunas originais
                    for col in df.columns:
                         if col != 'CNPJ':
                             dados_finais[col] = row.get(col)

                    if row_banco:
                        endereco_banco = row_banco.get("Endereco")
                        # Usa dados do banco se endereço for válido
                        if pd.notnull(endereco_banco) and str(endereco_banco).strip().lower() not in ["não encontrado", "cnpj inválido", "", ","]:
                            dados_finais.update({
                                'Endereco': endereco_banco,
                                'Status': row_banco.get("Status"),
                                'Telefone': row_banco.get("Telefone"),
                                'Email': row_banco.get("Email"),
                                'Latitude': row_banco.get("Latitude"),
                                'Longitude': row_banco.get("Longitude"),
                                'Google Maps': google_maps_link(endereco_banco)
                            })
                            logging.info(f"Dados para {cnpj} encontrados no banco.")

                    # 2. Se não achou no banco ou endereço inválido, busca na API
                    if not dados_finais['Endereco']:
                        logging.info(f"Buscando dados na API para {cnpj}...")
                        resultado_api = buscar_endereco_cnpj(cnpj)
                        # Monta endereço completo igual à busca individual
                        endereco_api = construir_endereco_completo(resultado_api)
                        situacao_api = resultado_api.get('situacao')
                        telefone_api = resultado_api.get('telefone')
                        email_api = resultado_api.get('email')

                        dados_finais['Status'] = situacao_cadastral_str(situacao_api)
                        dados_finais['Telefone'] = telefone_api
                        dados_finais['Email'] = email_api

                        if endereco_api:
                            dados_finais['Endereco'] = endereco_api
                            lat_api, lon_api = obter_coordenadas(endereco_api)
                            dados_finais['Latitude'] = lat_api
                            dados_finais['Longitude'] = lon_api
                            dados_finais['Google Maps'] = google_maps_link(endereco_api)
                        else:
                            dados_finais['Endereco'] = "Não encontrado"
                            dados_finais['Latitude'] = None
                            dados_finais['Longitude'] = None
                            dados_finais['Google Maps'] = ""

                    resultados.append(dados_finais)
                    cnpjs_processados += 1
                    progress.progress(cnpjs_processados / total_cnpjs)
                    # time.sleep(0.05) # Pausa mínima opcional

                progress.empty()
                status_text.empty()

                df_result = pd.DataFrame(resultados)

                # Garante a ordem das colunas principais e mantém as outras
                colunas_principais = [
                    "CNPJ", "Status", "Endereco", "Telefone", "Email",
                    "Google Maps", "Latitude", "Longitude"
                ]
                outras_colunas_originais = [c for c in df.columns if c != 'CNPJ']
                colunas_finais = colunas_principais + [c for c in outras_colunas_originais if c not in colunas_principais]
                # Adiciona colunas que podem ter sido criadas (caso raro)
                colunas_finais += [c for c in df_result.columns if c not in colunas_finais]

                df_result = df_result[colunas_finais]
                df_result = df_result.loc[:, ~df_result.columns.duplicated()]

                st.success("Processamento concluído!")
                st.dataframe(df_result, use_container_width=True, height=300)

                # Salva/Atualiza no banco de dados
                salvar_cnpj_enderecos(df_result)
                st.info(f"{len(df_result)} resultados salvos/atualizados no banco de dados local.")

                # Exibir mapa
                df_map = df_result.dropna(subset=["Latitude", "Longitude"]).copy()
                if not df_map.empty:
                    df_map["Latitude"] = pd.to_numeric(df_map["Latitude"], errors="coerce")
                    df_map["Longitude"] = pd.to_numeric(df_map["Longitude"], errors="coerce")
                    df_map = df_map.dropna(subset=["Latitude", "Longitude"])
                    if not df_map.empty:
                        st.map(df_map.rename(columns={"Latitude": "latitude", "Longitude": "longitude"}))
                    else:
                        st.write("Nenhum CNPJ com coordenadas válidas para exibir no mapa.")
                else:
                    st.write("Nenhum CNPJ com coordenadas válidas para exibir no mapa.")

                # Botão de download
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_result.to_excel(writer, index=False, sheet_name='CNPJs')
                    # Formata coluna CNPJ como texto no Excel
                    ws = writer.sheets['CNPJs']
                    try:
                        # Encontra a coluna CNPJ (pode não ser a primeira)
                        cnpj_col_idx = df_result.columns.get_loc('CNPJ') + 1
                        cnpj_col_letter = openpyxl.utils.get_column_letter(cnpj_col_idx)
                        for cell in ws[cnpj_col_letter]:
                            if cell.row > 1: # Pula cabeçalho
                                cell.number_format = '@' # Formato Texto
                    except Exception as e_format:
                        logging.warning(f"Erro ao formatar coluna CNPJ no Excel: {e_format}")
                output.seek(0)
                st.download_button(
                    label="💾 Baixar Resultado em Excel",
                    data=output.getvalue(),
                    file_name="cnpjs_com_dados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.toast("Busca em lote finalizada!")
                st.session_state.processing_cnpj = False
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento em lote: {e}")
                logging.error(f"Erro no processamento em lote: {e}", exc_info=True)
                st.session_state.processing_cnpj = False
                st.rerun()

    # --- Gerenciamento dos dados salvos ---
    st.divider()
    with st.container(border=True):
        st.subheader("📝 Gerenciar CNPJs Salvos")
        df_cnpj_raw = carregar_cnpj_enderecos()

        if df_cnpj_raw.empty:
            st.info("Nenhum CNPJ salvo no banco de dados ainda.")
        else:
            # Padroniza e garante colunas
            df_cnpj = df_cnpj_raw.copy()
            df_cnpj.columns = [str(col).strip() for col in df_cnpj.columns]
            col_renomear_lower = {}
            for col in df_cnpj.columns:
                col_lower = col.lower()
                if col_lower == 'cnpj' and col != 'CNPJ': col_renomear_lower[col] = 'CNPJ'
                elif col_lower == 'status' and col != 'Status': col_renomear_lower[col] = 'Status'
                elif col_lower in ['cód. edata', 'cod_edata', 'cod. edata'] and col != 'Cód. Edata': col_renomear_lower[col] = 'Cód. Edata'
                elif col_lower in ['cód. mega', 'cod_mega', 'cod. mega'] and col != 'Cód. Mega': col_renomear_lower[col] = 'Cód. Mega'
                elif col_lower == 'nome' and col != 'Nome': col_renomear_lower[col] = 'Nome'
                elif col_lower == 'endereco' and col != 'Endereco': col_renomear_lower[col] = 'Endereco'
                elif col_lower == 'telefone' and col != 'Telefone': col_renomear_lower[col] = 'Telefone'
                elif col_lower == 'email' and col != 'Email': col_renomear_lower[col] = 'Email'
                elif col_lower == 'latitude' and col != 'Latitude': col_renomear_lower[col] = 'Latitude'
                elif col_lower == 'longitude' and col != 'Longitude': col_renomear_lower[col] = 'Longitude'
                elif col_lower in ['google maps', 'googlemaps', 'maps'] and col != 'Google Maps': col_renomear_lower[col] = 'Google Maps'

            if col_renomear_lower:
                df_cnpj = df_cnpj.rename(columns=col_renomear_lower)

            df_cnpj = df_cnpj.loc[:, ~df_cnpj.columns.duplicated()]

            colunas_padrao = [
                'CNPJ', 'Status', 'Cód. Edata', 'Cód. Mega', 'Nome',
                'Endereco', 'Telefone', 'Email',
                'Latitude', 'Longitude', 'Google Maps'
            ]
            for col in colunas_padrao:
                if col not in df_cnpj.columns:
                    df_cnpj[col] = ''

            cols_existentes_ordenadas = [col for col in colunas_padrao if col in df_cnpj.columns]
            outras_cols = [col for col in df_cnpj.columns if col not in colunas_padrao]
            df_cnpj = df_cnpj[cols_existentes_ordenadas + outras_cols]

            # Limpa CNPJ para garantir consistência na chave do editor
            if 'CNPJ' in df_cnpj.columns:
                 df_cnpj['CNPJ'] = df_cnpj['CNPJ'].astype(str).str.replace(r'\D', '', regex=True).str.zfill(14)
            else:
                 st.error("Coluna CNPJ não encontrada após padronização. Não é possível editar.")
                 st.stop()

            # Filtros
            st.write("Filtre e edite os dados salvos:")
            col_filtros1, col_filtros2 = st.columns(2)
            with col_filtros1:
                filtro_texto = st.text_input("Filtrar por qualquer campo", key="filtro_cnpj_texto")
            with col_filtros2:
                # Garante que Status existe e não tem nulos para o filtro
                status_options = []
                if 'Status' in df_cnpj.columns:
                    status_options = df_cnpj['Status'].fillna('Não informada').unique().tolist()
                filtro_status = st.multiselect("Filtrar por Status", options=status_options, key="filtro_cnpj_status")

            df_filtrado = df_cnpj.copy()
            if filtro_texto:
                # Busca em todas as colunas convertidas para string
                df_filtrado = df_filtrado[df_filtrado.apply(lambda row: row.astype(str).str.contains(filtro_texto, case=False, na=False).any(), axis=1)]
            if filtro_status:
                if 'Status' in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado['Status'].fillna('Não informada').isin(filtro_status)]

            st.info(f"{len(df_filtrado)} de {len(df_cnpj)} CNPJs exibidos após filtros.")

            # Editor de dados
            df_editado = st.data_editor(
                df_filtrado,
                num_rows="dynamic",
                use_container_width=True,
                key="cnpj_editor",
                column_order=df_cnpj.columns.tolist(),
                hide_index=True,
                # Define a coluna CNPJ como índice (não editável) para estabilidade
                # disabled=["CNPJ"], # Desabilitar edição do CNPJ
                column_config={
                    "Google Maps": st.column_config.LinkColumn("Google Maps", display_text="Abrir Mapa"),
                    "Latitude": st.column_config.NumberColumn(format="%.6f"),
                    "Longitude": st.column_config.NumberColumn(format="%.6f"),
                }
            )

            # Botões de Ação
            col_botoes1, col_botoes2, col_botoes3 = st.columns(3)
            with col_botoes1:
                if st.button("💾 Salvar Edições", key="btn_salvar_edicoes", help="Salva as alterações feitas na tabela acima."):
                    # Identifica as linhas que foram realmente editadas comparando com o df_filtrado original
                    # Usa o CNPJ como índice para comparação segura
                    try:
                        df_filtrado_idx = df_filtrado.set_index('CNPJ')
                        df_editado_idx = df_editado.set_index('CNPJ')

                        # Compara os dataframes alinhados pelo índice
                        diff_mask = (df_filtrado_idx != df_editado_idx).any(axis=1)
                        cnpjs_alterados = diff_mask[diff_mask].index.tolist()

                        if not cnpjs_alterados:
                            st.warning("Nenhuma alteração detectada para salvar.")
                        else:
                            # Pega as linhas alteradas do df_editado
                            df_alterado = df_editado_idx.loc[cnpjs_alterados]

                            # Atualiza o df_cnpj original (que contém todos os dados)
                            df_cnpj_idx = df_cnpj.set_index('CNPJ')
                            df_cnpj_idx.update(df_alterado)
                            df_cnpj_atualizado = df_cnpj_idx.reset_index()

                            # Reaplicar a ordem original das colunas
                            df_cnpj_atualizado = df_cnpj_atualizado[df_cnpj.columns]

                            salvar_cnpj_enderecos(df_cnpj_atualizado)
                            st.success(f"{len(cnpjs_alterados)} CNPJs atualizados no banco de dados!")
                            st.rerun()

                    except Exception as e_save:
                        st.error(f"Erro ao salvar edições: {e_save}")
                        logging.error(f"Erro ao salvar edições do data_editor: {e_save}", exc_info=True)

            with col_botoes2:
                # Botão para buscar/atualizar dados para não localizados ou inválidos
                mask_atualizar = (
                    df_cnpj["Endereco"].isnull() |
                    (df_cnpj["Endereco"] == "") |
                    (df_cnpj["Endereco"].astype(str).str.strip().isin(["Não encontrado", "CNPJ inválido", ","])) |
                    (df_cnpj["Latitude"].isnull()) | (df_cnpj["Longitude"].isnull()) # Inclui os sem coordenadas
                )
                # Garante que CNPJ não seja nulo para processamento
                mask_atualizar &= df_cnpj["CNPJ"].notnull() & (df_cnpj["CNPJ"] != "")

                df_para_atualizar = df_cnpj[mask_atualizar].copy()
                total_atualizar = len(df_para_atualizar)
                label_btn_atualizar = f"🔄 Atualizar Dados ({total_atualizar})"
                if st.button(label_btn_atualizar, key="btn_buscar_faltantes", disabled=(total_atualizar == 0), help="Busca/Atualiza Endereço, Coords, Tel e Email para CNPJs marcados como 'Não encontrado', 'Inválido' ou sem coordenadas."):
                    progress = st.progress(0, text="Atualizando dados...")
                    cnpjs_atualizados_count = 0
                    df_cnpj_atualizado = df_cnpj.copy() # Trabalha em uma cópia

                    for idx, (i, row) in enumerate(df_para_atualizar.iterrows()):
                        cnpj = row["CNPJ"]
                        progress.progress((idx+1)/total_atualizar, text=f"Processando {idx+1}/{total_atualizar}: {cnpj}")

                        resultado_api = buscar_endereco_cnpj(cnpj)
                        endereco = resultado_api.get('endereco')
                        situacao = resultado_api.get('situacao')
                        telefone = resultado_api.get('telefone')
                        email = resultado_api.get('email')
                        link = ""
                        lat, lon = None, None

                        if endereco:
                            link = google_maps_link(endereco)
                            lat, lon = obter_coordenadas(endereco)
                            df_cnpj_atualizado.loc[i, "Endereco"] = endereco
                            df_cnpj_atualizado.loc[i, "Google Maps"] = link
                            df_cnpj_atualizado.loc[i, "Latitude"] = lat
                            df_cnpj_atualizado.loc[i, "Longitude"] = lon
                        else:
                            df_cnpj_atualizado.loc[i, "Endereco"] = "Não encontrado"
                            df_cnpj_atualizado.loc[i, "Google Maps"] = ""
                            df_cnpj_atualizado.loc[i, "Latitude"] = None
                            df_cnpj_atualizado.loc[i, "Longitude"] = None

                        df_cnpj_atualizado.loc[i, "Status"] = situacao_cadastral_str(situacao)
                        df_cnpj_atualizado.loc[i, "Telefone"] = telefone or ""
                        df_cnpj_atualizado.loc[i, "Email"] = email or ""

                        cnpjs_atualizados_count += 1

                    progress.empty()
                    if cnpjs_atualizados_count > 0:
                        # Salva o DataFrame completo, não só os atualizados
                        salvar_cnpj_enderecos(df_cnpj_atualizado)
                        st.success(f"Dados buscados/atualizados para {cnpjs_atualizados_count} CNPJs!")
                    else:
                        st.info("Nenhum CNPJ precisava de atualização.")
                    st.rerun()

            with col_botoes3:
                 # Botão Limpar dados salvos
                if st.button("🗑️ Limpar Banco", key="btn_limpar_cnpjs", type="primary", help="Apaga TODOS os CNPJs salvos localmente."):
                    # Adiciona confirmação extra
                    if 'confirm_delete' not in st.session_state:
                        st.session_state.confirm_delete = False

                    if st.session_state.confirm_delete:
                        limpar_cnpj_enderecos()
                        st.success("Banco de dados de CNPJs limpo!")
                        st.session_state.confirm_delete = False # Reseta confirmação
                        st.rerun()
                    else:
                        st.warning("Clique novamente para confirmar a exclusão de TODOS os dados.")
                        st.session_state.confirm_delete = True # Pede confirmação no próximo clique
                else:
                     st.session_state.confirm_delete = False # Reseta se o botão não for clicado

    # --- Busca individual ---
    st.divider()
    with st.container(border=True):
        st.subheader("👤 Busca Individual")
        cnpj_input = st.text_input("Digite o CNPJ", max_chars=18, help="Pontos, barras e traços são ignorados.", key="cnpj_individual")
        buscar_individual = st.button("🔍 Buscar CNPJ", key="buscar_individual_btn")

        if buscar_individual and cnpj_input:
            cnpj_limpo = re.sub(r'\D', '', cnpj_input).zfill(14)
            if len(cnpj_limpo) != 14:
                st.error("CNPJ inválido. Por favor, digite um CNPJ com 14 dígitos.")
            else:
                # 1. Buscar no banco
                row_banco = buscar_cnpj_no_banco(cnpj_limpo)
                dados_endereco = {}
                endereco_completo = None
                situacao, telefone, email = None, None, None
                nome_empresarial, ocorrencia_fiscal, regime_apuracao = None, None, None
                suframa_ativo = None
                numero_inscricao_suframa = None # Nova variável
                lat, lon = None, None
                fonte = ""

                if row_banco:
                    endereco_banco = row_banco.get("Endereco")
                    if pd.notnull(endereco_banco) and str(endereco_banco).strip().lower() not in ["não encontrado", "cnpj inválido", "", ","]:
                        # Se achou no banco, usa os dados de lá.
                        endereco_completo = endereco_banco
                        situacao = row_banco.get("Status")
                        telefone = row_banco.get("Telefone")
                        email = row_banco.get("Email")
                        nome_empresarial = row_banco.get("Nome") # Assumindo que 'Nome' no banco é o nome empresarial
                        ocorrencia_fiscal = row_banco.get("Ocorrencia Fiscal") # Adicionar se existir no banco
                        regime_apuracao = row_banco.get("Regime Apuracao") # Adicionar se existir no banco
                        suframa_ativo = row_banco.get("Suframa Ativo")
                        numero_inscricao_suframa = row_banco.get("Numero Inscricao Suframa") # Carrega do banco
                        lat = row_banco.get("Latitude")
                        lon = row_banco.get("Longitude")
                        dados_endereco = {'endereco_completo': endereco_completo} # Placeholder
                        fonte = "Banco de Dados Local"
                        st.info(f"Dados carregados do {fonte}.")

                # 2. Se não achou no banco ou endereço inválido, busca na API
                if not endereco_completo:
                    with st.spinner("Buscando dados do CNPJ via API..."):
                        dados_endereco = buscar_endereco_cnpj(cnpj_limpo)

                    situacao = dados_endereco.get('situacao')
                    telefone = dados_endereco.get('telefone')
                    email = dados_endereco.get('email')
                    nome_empresarial = dados_endereco.get('nome_empresarial')
                    ocorrencia_fiscal = dados_endereco.get('ocorrencia_fiscal')
                    regime_apuracao = dados_endereco.get('regime_apuracao')
                    suframa_ativo = dados_endereco.get('suframa_ativo')
                    numero_inscricao_suframa = dados_endereco.get('numero_inscricao_suframa') # Carrega da API
                    fonte = "API Externa"

                    # Constrói o endereço completo a partir dos componentes para obter coordenadas
                    endereco_completo = construir_endereco_completo(dados_endereco)

                    if endereco_completo:
                        with st.spinner("Buscando coordenadas..."):
                            lat, lon = obter_coordenadas(endereco_completo)
                    else:
                        lat, lon = None, None
                        if dados_endereco.get('situacao') == 'Inválido':
                            situacao = 'Inválido'

                # Exibe os resultados
                st.markdown(f"**Resultado para CNPJ:** `{cnpj_limpo}` (Fonte: {fonte})", unsafe_allow_html=True)
                if situacao == 'Inválido':
                     st.error(f"CNPJ {cnpj_limpo} parece ser inválido ou não encontrado.")
                # Verifica se temos pelo menos logradouro ou município para exibir algo
                elif dados_endereco.get('logradouro') or dados_endereco.get('municipio') or nome_empresarial: # Adicionado nome_empresarial na condição
                    # Exibe Nome Empresarial primeiro
                    st.markdown(f"🏢 **Nome Empresarial:** {nome_empresarial or 'Não informado'}")

                    # Monta a linha do logradouro
                    logradouro_str = dados_endereco.get('logradouro', '')
                    numero_str = dados_endereco.get('numero', '')
                    complemento_str = dados_endereco.get('complemento', '')
                    linha_logradouro = f"{logradouro_str}, {numero_str}" if numero_str else logradouro_str
                    if complemento_str:
                        linha_logradouro += f" - {complemento_str}"

                    # Monta a linha do município
                    municipio_str = dados_endereco.get('municipio', '')
                    uf_str = dados_endereco.get('uf', '')
                    linha_municipio = f"{municipio_str} - {uf_str}" if uf_str else municipio_str

                    st