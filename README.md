# Wazelog - Roteirizador de Entregas 🚚🗺️

Wazelog é uma plataforma moderna para roteirização inteligente de entregas, combinando backend FastAPI, frontend Streamlit e banco de dados local SQLite. Permite importar, editar, visualizar e gerenciar pedidos e frota, além de gerar e visualizar rotas otimizadas em mapas interativos.

## ✨ Funcionalidades
- Upload, edição e persistência de planilhas de frota e pedidos
- Busca automática de coordenadas (Nominatim/OpenCage)
- Edição manual e visualização dos dados
- Remoção e adição de registros
- Limpeza total dos pedidos e frota
- Visualização de mapas e dashboards
- Geração de rotas otimizadas (VRP, CVRP, VRPTW, TSP)
- Visualização de rotas por veículo/placa
- Exportação de anomalias para CSV

## 📦 Pré-requisitos
- Python 3.10+
- pip

## 🚀 Instalação
1. Clone o repositório:
   ```bash
   git clone https://github.com/OrlandoNavarro/WazeLog.git
   cd WazeLog
   ```
2. **Importante (Git LFS):** Este repositório usa Git Large File Storage (LFS) para arquivos grandes (como mapas `.osm.pbf`). Certifique-se de ter o Git LFS instalado ([https://git-lfs.github.com/](https://git-lfs.github.com/)) e execute `git lfs install` uma vez antes de prosseguir, se necessário. O Git LFS deve baixar os arquivos grandes automaticamente durante o clone ou checkout.
3. Instale as dependências Python:
   ```bash
   pip install -r requirements.txt
   ```

## 🏁 Como iniciar o projeto

A maneira mais fácil de iniciar todos os componentes do Wazelog (Servidor OSRM, Backend FastAPI e Frontend Streamlit) é usando o script `start_wazelog.sh`.

1.  **Torne o script executável (apenas uma vez):**
    ```bash
    chmod +x start_wazelog.sh
    ```
2.  **Execute o script:**
    ```bash
    ./start_wazelog.sh
    ```

**O que o script faz:**
*   Verifica e tenta liberar as portas 8000 (FastAPI) e 8501 (Streamlit) se estiverem em uso.
*   Inicia o servidor OSRM local usando Docker em background (usando o arquivo `routing/osrm_local/data/sao-paulo-latest.osm.pbf`).
    *   *Observação:* Na primeira execução do Docker, o pré-processamento do mapa pode levar um tempo considerável. Aguarde a conclusão.
*   Inicia o backend FastAPI em background na porta 8000.
*   Inicia o frontend Streamlit em primeiro plano na porta 8501.
*   Quando você interrompe o script (pressionando `Ctrl+C` no terminal onde o Streamlit está rodando), ele tenta parar o processo FastAPI e os containers Docker do OSRM automaticamente.

**Acesso:**
*   Backend FastAPI: http://localhost:8000
*   Frontend Streamlit: http://localhost:8501

**(Opcional) Execução Manual (se não usar o script):**

### 1. (Opcional, mas recomendado) Inicie o Servidor OSRM Local com Docker
   *   **Arquivo de Mapa:** Certifique-se de que o arquivo `routing/osrm_local/data/sao-paulo-latest.osm.pbf` existe. Se não existir, você pode baixá-lo ou usar outro arquivo `.osm.pbf` e ajustar o `docker-compose.yml` se necessário.
   *   **Iniciar:**
      ```bash
      # Navegue até o diretório
      cd /workspaces/WazeLog/routing/osrm_local/
      # Inicie (em background)
      docker-compose up -d
      # Volte para a raiz
      cd /workspaces/WazeLog/
      ```
   *   **Parar:**
      ```bash
      cd /workspaces/WazeLog/routing/osrm_local/ && docker-compose down
      ```

### 2. Inicie o backend FastAPI
   ```bash
   # Na raiz do projeto (/workspaces/WazeLog)
   python -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

### 3. Inicie o frontend Streamlit
   ```bash
   # Na raiz do projeto (/workspaces/WazeLog)
   python -m streamlit run app/app.py --server.port 8501
   ```

## 🗂️ Estrutura de Pastas
- `app/` - Código principal do Streamlit e módulos auxiliares
- `database/` - Banco SQLite local
- `data/` - Planilhas de exemplo ou dados de entrada
- `routing/` - Algoritmos de roteirização e otimização

## 💡 Observações
- O processamento de pedidos pode demorar devido à busca de coordenadas.
- O banco de dados é criado automaticamente em `database/wazelog.db`.
- Para uso em produção, configure variáveis de ambiente para as chaves de API do OpenCage.
- O sistema já traz um endereço de partida padrão, mas pode ser alterado na interface.
- Após a roteirização, visualize rotas por placa na aba "Mapas".

## 👨‍💻 Contribuição
Pull requests são bem-vindos! Para grandes mudanças, abra uma issue primeiro para discutir o que você gostaria de modificar.

---
Desenvolvido por Orlando e colaboradores.
Agradecemos a todos os contribuidores e usuários que tornam o Wazelog uma ferramenta melhor a cada dia! 🚀