import pytest

from mini3di_search.adapters.foldseek import Foldseek, inspect_pdb_backbone, read_fasta


def test_fasta_ids_are_joinable_not_order_dependent(tmp_path):
    p = tmp_path / "a.fasta"
    p.write_text(">b description\nAC\nD\n>a\nCX\n")
    assert read_fasta(p) == {"b": "ACD", "a": "CX"}
    for content in ("ACD\n", ">a\nAC\n>a\nCD\n", ">a\n", ">\nAC\n"):
        p.write_text(content)
        with pytest.raises(ValueError):
            read_fasta(p)


def test_binary_integrity_checked_before_execution(tmp_path):
    p = tmp_path / "binary"
    p.write_bytes(b"not an executable")
    with pytest.raises(ValueError, match="checksum"):
        Foldseek(p, "wrong")


def test_complete_backbone_policy(tmp_path):
    def atom(residue, name):
        return (
            f"ATOM  {residue:5d} {name:^4s} ALA A{residue:4d}    {1.0:8.3f}{2.0:8.3f}{3.0:8.3f}\n"
        )

    p = tmp_path / "structure"
    text = "".join(atom(i, a) for i in range(1, 4) for a in ("N", "CA", "C"))
    p.write_text(text)
    assert inspect_pdb_backbone(p) == {"A": 3}
    p.write_text("".join(atom(i, a) for i in range(1, 4) for a in ("CA", "C")))
    with pytest.raises(ValueError, match="missing"):
        inspect_pdb_backbone(p)
