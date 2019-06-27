# Tests for the various operations (GetItem, Query, Scan) with a
# ProjectionExpression parameter.
#
# ProjectionExpression is an expension of the legacy AttributesToGet
# parameter. Both parameters request that only a subset of the attributes
# be fetched for each item, instead of all of them. But while AttributesToGet
# was limited to top-level attributes, ProjectionExpression can request also
# nested attributes.

import random
import string
import pytest
import collections
from botocore.exceptions import ClientError

def random_string(length=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(length))

# Utility functions for scan and query into an array of items:
def full_scan(table, **kwargs):
    response = table.scan(**kwargs)
    items = response['Items']
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'], **kwargs)
        items.extend(response['Items'])
    return items

def full_query(table, **kwargs):
    response = table.query(**kwargs)
    items = response['Items']
    while 'LastEvaluatedKey' in response:
        response = table.query(ExclusiveStartKey=response['LastEvaluatedKey'], **kwargs)
        items.extend(response['Items'])
    return items

# To compare two lists of items (each is a dict) without regard for order,
# "==" is not good enough because it will fail if the order is different.
# The following function, multiset() converts the list into a multiset
# (set with duplicates) where order doesn't matter, so the multisets can
# be compared.
def multiset(items):
    return collections.Counter([frozenset(item.items()) for item in items])

# Basic test for ProjectionExpression, requesting only top-level attributes.
# Result should include the selected attributes only - if one wants the key
# attributes as well, one needs to select them explicitly. When no key
# attributes are selected, an item may have *none* of the selected
# attributes, and returned as an empty item.
@pytest.mark.xfail(reason="ProjectionExpression not yet implemented in GetItem")
def test_projection_expression_toplevel(test_table):
    p = random_string()
    c = random_string()
    item = {'p': p, 'c': c, 'a': 'hello', 'b': 'hi'}
    test_table.put_item(Item=item)
    for wanted in [ ['a'],             # only non-key attribute
                    ['c', 'a'],        # a key attribute (sort key) and non-key
                    ['p', 'c'],        # entire key
                    ['nonexistent']    # Our item doesn't have this
                   ]:
        got_item = test_table.get_item(Key={'p': p, 'c': c}, ProjectionExpression=",".join(wanted), ConsistentRead=True)['Item']
        expected_item = {k: item[k] for k in wanted if k in item}
        assert expected_item == got_item

# Various simple tests for ProjectionExpression's syntax, using only top-evel
# attributes.
@pytest.mark.xfail(reason="ProjectionExpression not yet implemented in GetItem")
def test_projection_expression_toplevel_syntax(test_table_s):
    p = random_string()
    test_table_s.put_item(Item={'p': p, 'a': 'hello', 'b': 'hi'})
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a')['Item'] == {'a': 'hello'}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='#name', ExpressionAttributeNames={'#name': 'a'})['Item'] == {'a': 'hello'}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a,b')['Item'] == {'a': 'hello', 'b': 'hi'}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression=' a  ,   b  ')['Item'] == {'a': 'hello', 'b': 'hi'}
    # It is not allowed to fetch the same top-level attribute twice (or in
    # general, list two overlapping attributes). We get an error like
    # "Invalid ProjectionExpression: Two document paths overlap with each
    # other; must remove or rewrite one of these paths; path one: [a], path
    # two: [a]".
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a,a')['Item']
    # A comma with nothing after it is a syntax error:
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a,')['Item']
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression=',a')['Item']
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a,,b')['Item']
    # An empty ProjectionExpression is not allowed. DynamoDB recognizes its
    # syntax, but then writes: "Invalid ProjectionExpression: The expression
    # can not be empty".
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='')['Item']

# The following two tests are similar to test_projection_expression_toplevel()
# which tested the GetItem operation - but these test Scan and Query.
# Both test ProjectionExpression with only top-level attributes.
@pytest.mark.xfail(reason="ProjectionExpression not yet implemented in Scan")
def test_projection_expression_scan(filled_test_table):
    table, items = filled_test_table
    for wanted in [ ['another'],       # only non-key attributes (one item doesn't have it!)
                    ['c', 'another'],  # a key attribute (sort key) and non-key
                    ['p', 'c'],        # entire key
                    ['nonexistent']    # none of the items have this attribute!
                   ]:
        got_items = full_scan(table,  ProjectionExpression=",".join(wanted))
        expected_items = [{k: x[k] for k in wanted if k in x} for x in items]
        assert multiset(expected_items) == multiset(got_items)

@pytest.mark.xfail(reason="ProjectionExpression not yet implemented in Query")
def test_projection_expression_query(test_table):
    p = random_string()
    items = [{'p': p, 'c': str(i), 'a': str(i*10), 'b': str(i*100) } for i in range(10)]
    with test_table.batch_writer() as batch:
        for item in items:
            batch.put_item(item)
    for wanted in [ ['a'],             # only non-key attributes
                    ['c', 'a'],        # a key attribute (sort key) and non-key
                    ['p', 'c'],        # entire key
                    ['nonexistent']    # none of the items have this attribute!
                   ]:
        got_items = full_query(test_table, KeyConditions={'p': {'AttributeValueList': [p], 'ComparisonOperator': 'EQ'}}, ProjectionExpression=",".join(wanted))
        expected_items = [{k: x[k] for k in wanted if k in x} for x in items]
        assert multiset(expected_items) == multiset(got_items)

# The previous tests all fetched only top-level attributes. They could all
# be written using AttributesToGet instead of ProjectionExpression (and,
# in fact, we do have similar tests with AttributesToGet in other files),
# but the previous test checked that the alternative syntax works correctly.
# The following test checks fetching more elaborate attribute paths from
# nested documents.
@pytest.mark.xfail(reason="ProjectionExpression does not yet support attribute paths")
def test_projection_expression_path(test_table_s):
    p = random_string()
    test_table_s.put_item(Item={
        'p': p,
        'a': {'b': [2, 4, {'x': 'hi', 'y': 'yo'}], 'c': 5},
        'b': 'hello' 
        })
    # Fetching the entire nested document "a" works, of course:
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a')['Item'] == {'a': {'b': [2, 4, {'x': 'hi', 'y': 'yo'}], 'c': 5}}
    # If we fetch a.b, we get only the content of b - but it's still inside
    # the a dictionary:
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b')['Item'] == {'a': {'b': [2, 4, {'x': 'hi', 'y': 'yo'}]}}
    # Similarly, fetching a.b[0] gives us a one-element array in a dictionary.
    # Note that [0] is the first element of an array.
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[0]')['Item'] == {'a': {'b': [2]}}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[2]')['Item'] == {'a': {'b': [{'x': 'hi', 'y': 'yo'}]}}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[2].y')['Item'] == {'a': {'b': [{'y': 'yo'}]}}
    # Trying to read any sort of non-existant attribute returns an empty item.
    # This includes a non-existing top-level attribute, an attempt to read
    # beyond the end of an array or a non-existant member of a dictionary, as
    # well as paths which begin with a non-existant prefix.
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='x')['Item'] == {}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[3]')['Item'] == {}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.x')['Item'] == {}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.x.y')['Item'] == {}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[3].x')['Item'] == {}
    # We can read multiple paths - the result are merged into one object
    # structured the same was as in the original item:
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[0],a.b[1]')['Item'] == {'a': {'b': [2, 4]}}
    assert test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[0],a.c')['Item'] == {'a': {'b': [2], 'c': 5}}
    # It is not allowed to read the same path multiple times. The error from
    # DynamoDB looks like: "Invalid ProjectionExpression: Two document paths
    # overlap with each other; must remove or rewrite one of these paths;
    # path one: [a, b, [0]], path two: [a, b, [0]]".
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a.b[0],a.b[0]')['Item']
    # Two paths are considered to "overlap" if the content of one path
    # contains the content of the second path. So requesting both "a" and
    # "a.b[0]" is not allowed.
    with pytest.raises(ClientError, match='ValidationException'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a,a.b[0]')['Item']

# It is not allowed to use both ProjectionExpression and its older cousin,
# AttributesToGet, together. If trying to do this, DynamoDB produces an error
# like "Can not use both expression and non-expression parameters in the same
# request: Non-expression parameters: {AttributesToGet} Expression
# parameters: {ProjectionExpression}
@pytest.mark.xfail(reason="ProjectionExpression not yet implemented in GetItem")
def test_projection_expression_and_attributes_to_get(test_table_s):
    p = random_string()
    test_table_s.put_item(Item={'p': p, 'a': 'hello', 'b': 'hi'})
    with pytest.raises(ClientError, match='ValidationException.*both'):
        test_table_s.get_item(Key={'p': p}, ConsistentRead=True, ProjectionExpression='a', AttributesToGet=['b'])['Item']