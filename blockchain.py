# coding: UTF-8

import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        #ジェネシスブロックを作る
        self.new_block(previous_hash = '1', proof = 100)

    def register_node(self, address):
        """
        ノードのリストに新しいノードを追加する
        :param address: Address of node. Eg. 'http://192.168.0.5:5000'
        """

        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def valid_chain(self, chain):
        """
        与えられたブロックチェーンが有効かどうかを判定

        :param chain: A blockchain
        :return: True if valid, False if not
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n-----------\n")
            # ブロックのハッシュが正しいことをチェックする
            last_block_hash = self.hash(last_block)
            if block['previous_hash'] != last_block_hash:
                return False

            # プルーフ・オブ・ワークが正しいことをチェックする
            if not self.valid_proof(last_block['proof'], block['proof'], last_block_hash):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        自分たちのチェーンをネットワーク内で最も長いものと置き換えることで競合を解決する、コンセンサスアルゴリズム

        :return: True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None

        # 自分たちのものより長いチェーンだけを探す
        max_length = len(self.chain)

        # ネットワーク内のすべてのノードからチェーンを取得して検証する
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # 長さが長く、チェーンが有効かどうかチェックする
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # 自分たちのものより長く有効なチェーンを見つけたとき、置き換える
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def new_block(self, proof, previous_hash):
        """
        新しいブロックを作り、チェーンに加える
        :param proof: <int> プルーフ・オブ・ワークアルゴリズムから得られるプルーフ
        :param previous_hash: (オプション) <str> 前のブロックのハッシュ
        :return: <dict> 新しいブロック
        """
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        #現在のトランザクションをリセット
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        次に採掘されるブロックに加える新しいトランザクションを作る
        :param sendar: <str> 送信者のアドレス
        :param recipient: <str> 受信者のアドレス
        :param amount: <int> 量
        :return: <int> このトランザクションを含むブロックのアドレス
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        # チェーンの最後のブロックをリターンする
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        ブロックの SHA-356 ハッシュを作る
        :param block: <dict> ブロック
        :return: <str>
        """

        #必ずディクショナリ（辞書型のオブジェクト）がソートされている必要がある。そうでないと、一貫性のないはっしゅとなってしまう。
        block_string = json.dumps(block, sort_keys = True).encode()
        return hashlib.sha256(block_string).hexdigest()


    def proof_of_work(self, last_block):
        """
        シンプルなプルーフ・オブ・ワークのアルゴリズム:
        - hash(pp') の最初の4つが0となるような p' を探す
        - p は1つ前のブロックのプルーフ、 p' は新しいブロックのプルーフ
        :param last_proof: <int>
        :return: <int>
        """

        last_proof = last_block['proof']
        last_hash = self.hash(last_block)

        proof = 0
        while self.valid_proof(last_proof, proof, last_hash) is False:
            proof += 1

        return proof

    @staticmethod
    def valid_proof(last_proof, proof, last_hash):
        """
        プルーフが正しいかを確認する: hash(last_proof, proof)の最初の4つが0となっているか？
        :param last_proof: <int> 前のプルーフ
        :param proof: <int> 現在のプルーフ
        :return: <bool> 正しければ true 、そうでなければ false
        """

        guess = f'{last_proof}{proof}{last_hash}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

# ノードを作る
# Flaskについてくわしくはこちらhttp://flask.pocoo.org/docs/0.12/quickstart/#a-minimal-application
app = Flask(__name__)

# このノードのグローバルにユニークなアドレスを作る
node_identifire = str(uuid4()).replace('-', '')

#ブロックチェーンクラスをインスタンス化する
blockchain = Blockchain()

# メソッドではGETで/mineエンドポイントを作る
@app.route('/mine', methods=['GET'])
def mine():
    # 次のプルーフを見つけるためプルーフ・オブ・ワークアルゴリズムを使用する
    last_block = blockchain.last_block
    proof = blockchain.proof_of_work(last_block)

    # プルーフを見つけたことに対する報酬を得る
    # 送信者は、採掘者が新しいコインを採掘したことを表すために"0"とする
    blockchain.new_transaction(
        sender = "0",
        recipient = node_identifire,
        amount = 1,
    )

    # チェーンに新しいブロックを加えることで、新しいブロックを採掘する
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': '新しいブロックを採掘しました',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

#メソッドはPOSTで/transactions/newエンドポイントを作る。メソッドはPOSTなのでデータを送信する
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # POSTされたデータに必要なデータがあるかを確認
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    #新しいトランザクションを作る
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'トランザクションはブロック {index} に追加されました'}
    return jsonify(response), 201

# メソッドはGETで、ブロックチェーンをリターンする/chainエンドポイントを作る
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/resister', methods = ['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

# port5000でサーバーを起動する
if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=500, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=5000)