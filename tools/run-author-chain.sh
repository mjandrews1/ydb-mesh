#!/bin/bash
# Wait for PubMed author-pass to finish, then run MARC author-pass (P3.5b).
# Usage: nohup ./run-author-chain.sh > ${YDB_MESH:-$HOME/ydb-mesh}/author-chain.log 2>&1 &
source /usr/local/etc/ydb_env_set
export LD_LIBRARY_PATH=/usr/local/lib/yottadb/r206/plugin/o/utf8:${LD_LIBRARY_PATH:-}
export PYTHONPATH=${YDB_MESH:-$HOME/ydb-mesh}
cd ${YDB_MESH:-$HOME/ydb-mesh}

echo "CHAIN wait for PubMed author_pass … $(date -Is)"
while pgrep -f 'tools/author_pass.py' >/dev/null 2>&1; do
  sleep 30
done
echo "CHAIN PubMed pass done $(date -Is)"
tail -3 ${YDB_MESH:-$HOME/ydb-mesh}/author-pass.log

echo "CHAIN MARC catplus … $(date -Is)"
${YDB_PY:-$HOME/ydb-py/.venv/bin/python3} tools/author_pass.py \
  --marc '${DATA:-$HOME/_data}/nlm-staging/catplus-marcxml/*.xml.gz' \
  --kind catline | tee -a ${YDB_MESH:-$HOME/ydb-mesh}/author-marc-catplus.log

echo "CHAIN MARC serfile … $(date -Is)"
${YDB_PY:-$HOME/ydb-py/.venv/bin/python3} tools/author_pass.py \
  --marc '${DATA:-$HOME/_data}/nlm-staging/serfile-marcxml/*.xml.gz' \
  --kind serline | tee -a ${YDB_MESH:-$HOME/ydb-mesh}/author-marc-serfile.log

echo "CHAIN DONE $(date -Is)"

