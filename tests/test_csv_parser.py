import pytest
import os
import logging
from csv_to_xml_converter.csv_parser import parse_csv, parse_csv_from_profile, CSVParsingError


def test_csv_parser(tmp_path):
    logging.basicConfig(level=logging.DEBUG)
    # Prepare CSV files
    csv_content_basic = "name,age,city\nAlice,30,New York\nBob,25,Los Angeles"
    csv_path_basic = tmp_path / "basic.csv"
    csv_path_basic.write_text(csv_content_basic, encoding="utf-8")

    csv_content_tab = "name\tage\tcity\nCarol\t40\tChicago\nDave\t35\tHouston"
    csv_path_tab = tmp_path / "tab.csv"
    csv_path_tab.write_text(csv_content_tab, encoding="utf-8")

    sjis_name = "名前".encode('shift_jis').decode('shift_jis')
    sjis_age = "年齢".encode('shift_jis').decode('shift_jis')
    sjis_city = "都市".encode('shift_jis').decode('shift_jis')
    sjis_data_row1_name = "山田太郎".encode('shift_jis').decode('shift_jis')
    sjis_data_row1_age = "45".encode('shift_jis').decode('shift_jis')
    sjis_data_row1_city = "東京".encode('shift_jis').decode('shift_jis')
    csv_content_sjis = f"{sjis_name},{sjis_age},{sjis_city}\n{sjis_data_row1_name},{sjis_data_row1_age},{sjis_data_row1_city}"
    csv_path_sjis = tmp_path / "sjis.csv"
    csv_path_sjis.write_text(csv_content_sjis, encoding="shift_jis")

    csv_content_missing_col = "name,city\nEve,50,Miami"
    csv_path_missing_col = tmp_path / "missing.csv"
    csv_path_missing_col.write_text(csv_content_missing_col, encoding="utf-8")

    csv_content_comments = """# comment\nname,value\n# c2\n\nitemA,100\n\nitemB,200\n# end"""
    csv_path_comments = tmp_path / "comments.csv"
    csv_path_comments.write_text(csv_content_comments, encoding="utf-8")

    csv_content_quotes = 'name,notes\n"Smith, John","He said ""Hi"""\nJane,""Hello""'
    csv_path_quotes = tmp_path / "quotes.csv"
    csv_path_quotes.write_text(csv_content_quotes, encoding="utf-8")

    csv_content_single_quote = "name,desc\n'Alice','goodbye, friend'"
    csv_path_single_quote = tmp_path / "single.csv"
    csv_path_single_quote.write_text(csv_content_single_quote, encoding="utf-8")

    csv_content_escape = 'name\n"A\\"lice"'
    csv_path_escape = tmp_path / "escape.csv"
    csv_path_escape.write_text(csv_content_escape, encoding="utf-8")

    records1 = parse_csv(str(csv_path_basic))
    assert len(records1) == 2
    assert records1[0] == {"name": "Alice", "age": "30", "city": "New York"}

    records2 = parse_csv(str(csv_path_tab), delimiter="\t")
    assert records2[0] == {"name": "Carol", "age": "40", "city": "Chicago"}

    records3 = parse_csv(str(csv_path_sjis), encoding="shift_jis")
    assert records3[0][sjis_name] == sjis_data_row1_name

    with pytest.raises(CSVParsingError):
        parse_csv(str(csv_path_missing_col), required_columns=["name", "age", "city"])

    records5 = parse_csv(str(csv_path_comments))
    assert len(records5) == 2
    assert records5[1] == {"name": "itemB", "value": "200"}

    records6 = parse_csv(csv_content_basic)
    assert records6[0]["name"] == "Alice"

    records_quotes = parse_csv(str(csv_path_quotes))
    assert records_quotes[0] == {"name": "Smith, John", "notes": "He said \"Hi\""}

    records_single = parse_csv(str(csv_path_single_quote), quotechar="'")
    assert records_single[0] == {"name": "Alice", "desc": "goodbye, friend"}

    records_escape = parse_csv(str(csv_path_escape), escapechar="\\", doublequote=False)
    assert records_escape[0] == {"name": 'A"lice'}

    profile_test = {
        "source": str(csv_path_basic),
        "delimiter": ",",
        "encoding": "utf-8",
        "required_columns": ["name", "age"],
    }
    records7 = parse_csv_from_profile(profile_test)
    assert len(records7) == 2

    with pytest.raises(ValueError):
        parse_csv_from_profile({"delimiter": ","})

    profile_no_cols = {"source": "dummy\n1,2", "has_header": False}
    with pytest.raises(ValueError):
        parse_csv_from_profile(profile_no_cols)

    profile_req_missing = {
        "source": "dummy\n1,2,3",
        "has_header": False,
        "column_names": ["colA", "colB"],
        "required_columns": ["colA", "colC"],
    }
    with pytest.raises(CSVParsingError):
        parse_csv_from_profile(profile_req_missing)

    csv_path_no_header = tmp_path / "no_header.csv"
    csv_path_no_header.write_text("valA1,valB1\nvalA2,valB2", encoding="utf-8")
    profile_valid = {
        "source": str(csv_path_no_header),
        "has_header": False,
        "column_names": ["colA", "colB"],
        "required_columns": ["colA"],
    }
    records8_3 = parse_csv_from_profile(profile_valid)
    assert records8_3[0] == {"colA": "valA1", "colB": "valB1"}

    csv_path_no_header_req = tmp_path / "no_header_req.csv"
    csv_path_no_header_req.write_text("valX,valY\nvalZ,valW", encoding="utf-8")
    profile_valid_req = {
        "source": str(csv_path_no_header_req),
        "has_header": False,
        "column_names": ["headerX", "headerY"],
        "required_columns": ["headerX"],
    }
    records8_4 = parse_csv_from_profile(profile_valid_req)
    assert records8_4[1] == {"headerX": "valZ", "headerY": "valW"}

    csv_path_no_header_quotes = tmp_path / "no_header_quotes.csv"
    csv_path_no_header_quotes.write_text('"v1","v2"\n"v3","v4"', encoding="utf-8")
    profile_quotes = {
        "source": str(csv_path_no_header_quotes),
        "has_header": False,
        "column_names": ["col1", "col2"],
    }
    rec_quotes = parse_csv_from_profile(profile_quotes)
    assert rec_quotes[1] == {"col1": "v3", "col2": "v4"}

    with pytest.raises(FileNotFoundError):
        parse_csv("non_existent_file.csv")

    csv_content_mismatch = "header1,header2\ndata1\ndata1,data2,data3"
    records10 = parse_csv(csv_content_mismatch)
    assert len(records10) == 0

    # UTF-8 BOM file should decode correctly even with wrong encoding specified
    bom_csv = tmp_path / "bom.csv"
    bom_csv.write_text("name,age\nAmy,22", encoding="utf-8-sig")
    records_bom = parse_csv(str(bom_csv), encoding="shift_jis")
    assert records_bom[0] == {"name": "Amy", "age": "22"}


def test_parse_csv_from_profile_file_not_found():
    profile = {"source": "does_not_exist.csv"}
    with pytest.raises(FileNotFoundError):
        parse_csv_from_profile(profile)
