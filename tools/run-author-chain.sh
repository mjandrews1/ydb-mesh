#!/bin/bash
# Wait for PubMed author-pass to finish, then run MARC author-pass (P3.5b).
# Usage: nohup ./run-author-chain.sh > /home/mark/ydb-mesh/author-chain.log 2>&1 &
source /usr/local/etc/ydb_env_set
export LD_LIBRARY_PATH=/usr/local/lib/yottadb/r206/plugin/o/utf8:${LD_LIBRARY_PATH:-}
export PYTHONPATH=/home/mark/ydb-mesh
cd /home/mark/ydb-mesh

echo "CHAIN wait for PubMed author_pass … $(date -Is)"
while pgrep -f 'tools/author_pass.py' >/dev/null 2>&1; do
  sleep 30
done
echo "CHAIN PubMed pass done $(date -Is)"
tail -3 /home/mark/ydb-mesh/author-pass.log

echo "CHAIN MARC catplus … $(date -Is)"
/home/mark/ydb-py/.venv/bin/python3 tools/author_pass.py \
  --marc '/home/mark/_data/nlm-staging/catplus-marcxml/*.xml.gz' \
  --kind catline | tee -a /home/mark/ydb-mesh/author-marc-catplus.log

echo "CHAIN MARC serfile … $(date -Is)"
/home/mark/ydb-py/.venv/bin/python3 tools/author_pass.py \
  --marc '/home/mark/_data/nlm-staging/serfile-marcxml/*.xml.gz' \
  --kind serline | tee -a /home/mark/ydb-mesh/author-marc-serfile.log

echo "CHAIN DONE $(date -Is)"

