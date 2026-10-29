"""Ponte MCP di Tokyn: il piccolo server MCP che Claude Code avvia per usare gli strumenti di un agente.

Legge le richieste JSON-RPC da stdin e passa ogni chiamata a uno strumento al programma Tokyn, tramite il socket
su localhost protetto dal token scritto in tools.json: così gli strumenti vengono eseguiti nel processo del
programma e vedono le stesse variabili. Usa solo la libreria standard.

Uso: python ponte_mcp.py tools.json
Nei programmi autonomi (tokyn build --standalone) questo codice è incluso nel programma, che fa da ponte
quando viene avviato con: python programma.py --tokyn-ponte tools.json
"""

import json as _json
import socket
import sys


def _ponte_rispondi(rid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": rid}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(_json.dumps(msg) + "\n")
    sys.stdout.flush()


def servi_ponte(percorso_strumenti):
    """Risponde a Claude Code finché non chiude stdin. percorso_strumenti: il tools.json scritto dal runtime."""
    with open(percorso_strumenti, encoding="utf-8") as f:
        cfg = _json.load(f)
    # MCP su stdio è sempre UTF-8: senza questo su Windows le lettere accentate negli argomenti arriverebbero storpiate
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        if not line.strip():
            continue
        req = _json.loads(line)
        rid, method = req.get("id"), req.get("method")
        if rid is None:
            continue
        if method == "initialize":
            version = req.get("params", {}).get("protocolVersion", "2025-06-18")
            _ponte_rispondi(rid, {"protocolVersion": version, "capabilities": {"tools": {}},
                                  "serverInfo": {"name": "tokyn", "version": "1"}})
        elif method == "tools/list":
            _ponte_rispondi(rid, {"tools": cfg["tools"]})
        elif method == "tools/call":
            with socket.create_connection(("127.0.0.1", cfg["port"])) as conn:
                conn.sendall((_json.dumps({"token": cfg["token"], "call": req["params"]}) + "\n").encode("utf-8"))
                answer = _json.loads(conn.makefile(encoding="utf-8").readline())
            _ponte_rispondi(rid, {"content": [{"type": "text", "text": answer["text"]}], "isError": answer["error"]})
        elif method == "ping":
            _ponte_rispondi(rid, {})
        else:
            _ponte_rispondi(rid, error={"code": -32601, "message": "metodo sconosciuto: " + str(method)})
    return 0


if __name__ == "__main__":
    sys.exit(servi_ponte(sys.argv[1]))
