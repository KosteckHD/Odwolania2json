"""Local synthetic Chat Completions server for frontend integration."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text = request["messages"][-1]["content"].casefold()
        if "potwierdzenie" in text and "przelew" in text:
            data = {"przelew_bankowy": {"data_operacji": None, "kwota": None, "na_rachunek": None,
                                        "numer_transakcji": None, "tytul": None, "z_rachunku": None}}
            result = {"typ": "przelew", "dane": data}
        else:
            result = {"typ": "unknown", "dane": None}
        body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
