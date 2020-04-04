from flask import Flask, jsonify, request
from agricolaenvironment.agricola.game import StandardAgricolaGame, TextInterface, play
import json
import uuid
import elasticsearch
app = Flask(__name__)

LOG_DIR = "./logs"
ELASTICSEARCH_ENDPOINT = "https://search-agricola-games-l7ju4eul22s6c4n44sltpq4v6m.ap-northeast-1.es.amazonaws.com"
GAME_INDEX_NAME = "games"
GAME_HISTORY_INDEX_NAME = "game_histories"

@app.route("/", methods=['GET'])
def hello():
    return "Hello World!"

@app.route('/reply', methods=['POST'])
def reply():
    data = json.loads(request.data)
    answer = "Yes, it is %s!\n" % data["keyword"]
    result = {
      "Content-Type": "application/json",
      "Answer":{"Text": answer}
    }
    # return answer
    return jsonify(result)

@app.route('/game/<game_id>', methods=['GET'])
def getGame(game_id=None):
    client = elasticsearch.Elasticsearch(ELASTICSEARCH_ENDPOINT, use_ssl=False, verify_certs=False)
    res = client.get(index=GAME_INDEX_NAME, doc_type="_all", id=game_id)
    return jsonify(res["_source"]["next_input"])

# return history of specified agricola game
@app.route('/game/history/<game_id>', methods=['GET'])
def getGameHistory(game_id=None):
    client = elasticsearch.Elasticsearch(ELASTICSEARCH_ENDPOINT, use_ssl=False, verify_certs=False)
    res = client.search(index=GAME_HISTORY_INDEX_NAME, size=1000, body={"query": {"match": {"game.game_id":game_id}}})
    return jsonify([hit["_source"]["next_input"] for hit in res["hits"]["hits"]])

@app.route('/game/<game_id>', methods=['POST'])
def postGameAction(game_id=None):
    client = elasticsearch.Elasticsearch(ELASTICSEARCH_ENDPOINT, use_ssl=False, verify_certs=False)
    res = client.get(index=GAME_INDEX_NAME, doc_type="_all", id=game_id)
    
    game = StandardAgricolaGame(4, game_id)
    ui = TextInterface()

    print("input is:" + str(request.get_data()))

    next_state, next_input = play(game, ui, None, LOG_DIR, json.dumps(res["_source"]["game"]), step_execution=True, next_choice_output=request.get_data())
    
    # Save latest game data
    save_data = {
        "game": json.loads(next_state),
        "next_input": json.loads(next_input),
    }
    client.index(index=GAME_INDEX_NAME, doc_type='_doc', id=game_id, body=save_data)

    # Save history data
    res["_source"]["next_input"]["player_output"] = json.loads(request.get_data())
    save_history_data = {
        "game": res["_source"]["game"],
        "next_input": res["_source"]["next_input"],
    }
    client.index(index=GAME_HISTORY_INDEX_NAME, doc_type='_doc', id="%s-%d" % (game_id, res["_source"]["next_input"]["current_step_idx"]), body=save_history_data)

    result = {
      "Content-Type": "application/json",
      "game_id": game_id,
    }
    # return answer
    return jsonify(result)

@app.route('/game', methods=['POST'])
def createNewGame():

    # create game and save state
    game_id = str(uuid.uuid4())
    game = StandardAgricolaGame(4, game_id)
    ui = TextInterface()
    next_state, next_input = play(game, ui, None, LOG_DIR, None, step_execution=True, next_choice_output=None)

    save_data = {
        "game": json.loads(next_state),
        "next_input": json.loads(next_input),
    }

    # save next_state and next_input
    # TODO use SSL and certs
    client = elasticsearch.Elasticsearch(ELASTICSEARCH_ENDPOINT, use_ssl=False, verify_certs=False)
    client.index(index=GAME_INDEX_NAME, doc_type='_doc', id=game_id, body=save_data)


    result = {
      "Content-Type": "application/json",
      "game_id": game_id,
    }
    # return answer
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=5000,debug=True)
