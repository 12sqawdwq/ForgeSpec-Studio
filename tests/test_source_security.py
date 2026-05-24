from source_security import validate_cad_source


def test_source_security_rejects_banned_import():
    result = validate_cad_source(
        "import os\n"
        "def build_model():\n"
        "    os.system('whoami')\n"
        "def export_outputs(out_dir):\n"
        "    return {}\n"
    )
    assert not result.ok
    assert "banned_import:os" in result.errors


def test_source_security_rejects_dynamic_execution():
    result = validate_cad_source(
        "import cadquery as cq\n"
        "def build_model():\n"
        "    eval('1+1')\n"
        "def export_outputs(out_dir):\n"
        "    return {}\n"
    )
    assert not result.ok
    assert "banned_call:eval" in result.errors


def test_source_security_accepts_minimal_cadquery_source():
    result = validate_cad_source(
        "import cadquery as cq\n"
        "def build_model():\n"
        "    return cq.Workplane('XY').box(1, 1, 1).val()\n"
        "def export_outputs(out_dir):\n"
        "    return {}\n"
    )
    assert result.ok
