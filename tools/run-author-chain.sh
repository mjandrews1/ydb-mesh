#!/bin/bash
# P3.5b: MARC author-pass after PubMed author_pass exits
export ydb_dist=/usr/local/lib/yottadb/r206
export PATH=/usr/local/lib/yottadb/r206:/usr/local/bin:/usr/bin:/bin
source /usr/local/etc/ydb_env_set || true
export LD_LIBRARY_PATH=/usr/local/lib/yottadb/r206/plugin/o/utf8:${LD_LIBRARY_PATH:-}
export PYTHONPATH=/home/mark/ydb-mesh
cd /home/mark/ydb-mesh
echo "CHAIN waiting for PubMed $(date -Is)"
while pgrep -f "tools/author_pass.py" >/dev/null; do sleep 20; done
echo "CHAIN PubMed done $(date -Is)"
tail -2 /home/mark/ydb-mesh/author-pass.log
echo "CHAIN catplus $(date -Is)"
/home/mark/ydb-py/.venv/bin/python3 tools/author_pass.py --marc "/home/mark/_data/nlm-staging/catplus-marcxml/*.xml.gz" --kind catline
echo "CHAIN serfile $(date -Is)"
/home/mark/ydb-py/.venv/bin/python3 tools/author_pass.py --marc "/home/mark/_data/nlm-staging/serfile-marcxml/*.xml.gz" --kind serline
echo "CHAIN DONE $(date -Is)"
