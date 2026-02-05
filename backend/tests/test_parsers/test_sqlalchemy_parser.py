import os
import pytest

def test_parse_simple_sqlalchemy_models():
    """Test parsing simple SQLAlchemy models"""
    from parsers.sqlalchemy_parser import SQLAlchemyParser

    fixture_path = os.path.join(os.path.dirname(__file__), '..', 'fixtures', 'sqlalchemy_simple')
    parser = SQLAlchemyParser()
    result = parser.parse(fixture_path)

    # Should find 2 tables
    assert len(result['tables']) == 2

    # Check users table
    users_table = next(t for t in result['tables'] if t['name'] == 'users')
    assert users_table['name'] == 'users'
    assert len(users_table['columns']) == 3

    # Check id column is primary key
    id_col = next(c for c in users_table['columns'] if c['name'] == 'id')
    assert id_col['primary_key'] == True
    assert id_col['type'] == 'Integer'

    # Check username is unique
    username_col = next(c for c in users_table['columns'] if c['name'] == 'username')
    assert username_col['unique'] == True

    # Check posts table
    posts_table = next(t for t in result['tables'] if t['name'] == 'posts')
    assert posts_table['name'] == 'posts'

    # Check foreign key
    assert len(posts_table['foreign_keys']) == 1
    fk = posts_table['foreign_keys'][0]
    assert fk['column'] == 'author_id'
    assert fk['references_table'] == 'users'
    assert fk['references_column'] == 'id'

    # Check relationships
    assert len(result['relationships']) >= 1
    rel = next(r for r in result['relationships'] if r['from'] == 'posts')
    assert rel['to'] == 'users'
    assert rel['type'] == 'many-to-one'
