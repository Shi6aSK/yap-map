from app.services.concept_extractor import extract_concepts


def test_extract_basic_concepts():
    text = "We should use React Flow for the graph UI because it already supports nodes and edges."
    result = extract_concepts(text, segment_id='seg-1')

    types = [n['type'] for n in result['nodes']]

    # expect at least one action_item, one topic, and one claim
    assert 'action_item' in types
    assert 'topic' in types
    assert 'claim' in types
