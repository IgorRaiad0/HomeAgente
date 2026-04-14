from integrations.ha_rest import get_states, call_service

def list_entities():

    states = get_states()

    entities = []

    for s in states:
        entities.append(s["entity_id"])

    return entities


def turn_on(entity_id):

    domain = entity_id.split(".")[0]

    return call_service(domain, "turn_on", entity_id)


def turn_off(entity_id):

    domain = entity_id.split(".")[0]

    return call_service(domain, "turn_off", entity_id)