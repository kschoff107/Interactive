import os

def test_detect_sqlalchemy():
    """Test detecting SQLAlchemy project"""
    from parsers.parser_manager import ParserManager

    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'sqlalchemy_simple')
    manager = ParserManager()

    language, framework = manager.detect_language_and_framework(fixture_path)

    assert language == 'python'
    assert framework == 'sqlalchemy'

def test_parse_database_schema():
    """Test parsing database schema"""
    from parsers.parser_manager import ParserManager

    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'sqlalchemy_simple')
    manager = ParserManager()

    result = manager.parse_database_schema(fixture_path, 'python', 'sqlalchemy')

    assert 'tables' in result
    assert len(result['tables']) == 2
