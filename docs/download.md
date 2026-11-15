# Download das cenas NISAR GCOV

Cada arquivo GCOV tem aproximadamente 3,8 GB. O download deve ser feito em
um ambiente com conexão adequada, como um Codespace.

## Usando o script do projeto

1. Configure um secret do Codespaces chamado EARTHDATA_TOKEN. Não salve o
   token no repositório nem em histórico de shell.
2. Instale os requisitos do pipeline:

       python -m pip install -r requirements-pipeline.txt

3. Execute o downloader:

       python pipeline/download_gcov.py

O script busca os dois granules configurados para 5 e 17 de janeiro de 2026
e salva os HDF5 em data/, ignorado pelo Git. O registro de execução disponível
foi feito com asf_search 14.1.0; mudanças futuras na API ASF podem exigir
ajustes.

## Alternativa manual com wget

Copie a URL de cada cena no ASF Vertex e baixe-a com o token Earthdata
configurado no ambiente:

    wget --header="Authorization: Bearer $EARTHDATA_TOKEN" -P data/ "<URL_FROM_VERTEX>"

Se o servidor devolver 401/403, siga o fluxo de autenticação oficial da ASF
ou use o mecanismo Earthdata recomendado para o seu ambiente. Não publique
token, senha ou arquivo de credenciais.

Para continuar com conversão, detecção e validação, siga o
[pipeline de dados](technical/pipeline.md).
