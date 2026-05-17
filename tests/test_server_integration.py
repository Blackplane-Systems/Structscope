import json
import subprocess
import sys


def run_integration():
    proc = subprocess.Popen(
        [sys.executable, "python/server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    def rpc(req):
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    try:
        assert rpc({"method": "ping"}) == {"pong": True}, "ping failed"

        platforms = rpc({"method": "platforms"})
        assert "platforms" in platforms and "x86_64" in platforms["platforms"]
        assert "x86_64_windows" in platforms["platforms"]

        detected = rpc({"method": "detect_platform"})
        assert detected["platform"] in platforms["platforms"], detected

        src = "struct Foo { int a; char b; double c; };"
        response = rpc(
            {
                "method": "analyse",
                "source": src,
                "language": "c",
                "platform": "x86_64",
                "cache_line": 64,
            }
        )
        assert "structs" in response, response
        assert len(response["structs"]) >= 1
        structs_by_name = {s["name"]: s for s in response["structs"]}
        assert "Foo" in structs_by_name, structs_by_name.keys()
        foo = structs_by_name["Foo"]
        assert foo["layout"]["total_size"] == 16, foo
        assert foo["layout"]["fields"][0]["offset"] == 0, foo
        assert foo["layout"]["fields"][1]["offset"] == 4, foo
        assert foo["layout"]["fields"][2]["offset"] == 8, foo
        assert foo["analysis"]["waste_bytes"] > 0

        auto = rpc(
            {
                "method": "analyse",
                "source": src,
                "language": "c",
                "platform": "auto",
                "cache_line": 64,
            }
        )
        assert auto["platform"] in platforms["platforms"], auto
        assert auto["requested_platform"] == "auto", auto
        assert auto["structs"][0]["analysis"]["rules"] is not None
        assert auto["source_model"]["preprocessor"] is False

        comparison = rpc(
            {
                "method": "compare_platforms",
                "source": "struct Ptr { char tag; void *p; char tail; };",
                "language": "c",
                "platforms": ["x86_64", "arm32"],
                "cache_line": 64,
            }
        )
        ptr_summary = comparison["summary"]["Ptr"]
        assert ptr_summary["by_platform"]["x86_64"]["total_size"] != ptr_summary["by_platform"]["arm32"]["total_size"]
    finally:
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=5)


def test_server_integration():
    run_integration()


if __name__ == "__main__":
    run_integration()
    print("Integration test PASSED")
