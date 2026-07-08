from trading_storage.migrations import split_sql_statements


def test_split_sql_statements_keeps_quoted_semicolons() -> None:
    sql = "CREATE TABLE x (a String DEFAULT 'a;b'); CREATE TABLE y (b Int64);"
    statements = split_sql_statements(sql)
    assert len(statements) == 2
    assert "'a;b'" in statements[0]
    assert statements[1].startswith("CREATE TABLE y")
