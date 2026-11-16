# Downloading the NISAR GCOV scenes

Each GCOV file is about 3.8 GB. Download them in an environment with a good
connection, such as a Codespace.

## With the project script

1. Set a Codespaces secret called EARTHDATA_TOKEN. Do not save the token in
   the repository or in the shell history.
2. Install the pipeline requirements:

       python -m pip install -r requirements-pipeline.txt

3. Run the downloader:

       python pipeline/download_gcov.py

The script fetches the two granules configured for 5 and 17 January 2026 and
saves the HDF5 files in data/, which Git ignores. The recorded run used
asf_search 14.1.0; future changes to the ASF API may need adjustments.

## Manual alternative with wget

Copy the URL of each scene from ASF Vertex and download it with the Earthdata
token set in the environment:

    wget --header="Authorization: Bearer $EARTHDATA_TOKEN" -P data/ "<URL_FROM_VERTEX>"

If the server answers 401/403, follow ASF's official authentication flow or
use the Earthdata mechanism recommended for your environment. Never publish a
token, password or credentials file.

To continue with conversion, detection and validation, follow the
[data pipeline](technical/pipeline.md).
