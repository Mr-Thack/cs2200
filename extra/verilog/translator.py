import hashlib
import time
import base64
import json

def sha256ify(input_string):
    """Direct Translation of the Java sha256ify method from the origianl RA4King Source Code"""
    return hashlib.sha256(input_string.encode('utf-8')).hexdigest()

def generate_genesis_signature(circuits_dict):
    # 1. The Payload: Replicate GSON's no-space serialization
    # Assuming libraryPaths is an empty array []
    json_str = json.dumps(circuits_dict, indent=2)
    file_data = "null" + json_str.replace('\r\n', '\n')

    print("File Data:")
    print(file_data) 

    # 2. Hash the payload
    file_data_hash = sha256ify(file_data)
    print("File Data Hash:", file_data_hash)

    # 3. The Timestamp (Unix milliseconds)
    timestamp = str(int(time.time() * 1000))

    # 4. The Block Hash (previousHash + fileDataHash + timeStamp + copiedBlocks)
    # For the Genesis block, previousHash and copiedBlocks are empty strings ""
    raw_block_string = "" + file_data_hash + timestamp + ""
    print("Block Data:", raw_block_string) 
    current_hash = sha256ify(raw_block_string)
    print("Block Hash:", current_hash)

    # 5. Build and Base64 Encode the final string
    # Format: previousHash \t currentHash \t timeStamp \t fileDataHash
    final_string = f"\t{current_hash}\t{timestamp}\t{file_data_hash}"
    encoded_signature = base64.b64encode(final_string.encode('utf-8')).decode('utf-8')

    return encoded_signature


if __name__ == "__main__":
    dummy_circuits = [{
        "name": "CircuitMain",
        "components": [
            {
                "name": "com.ra4king.circuitsim.gui.peers.arithmetic.AdderPeer",
                "x": 15,
                "y": 15,
                "properties": {
                    "Label location": "NORTH",
                    "Label": "",
                    "Bitsize": "32"
                }
            },
            {
                "name": "com.ra4king.circuitsim.gui.peers.wiring.Tunnel",
                "x": 15 - 6,
                "y": 15,
                "properties": {
                    "Label": "W_000A",
                    "Direction": "EAST",
                    "Width": "4",
                    "Bitsize": "32"
                }
            },
            {
                "name": "com.ra4king.circuitsim.gui.peers.wiring.Tunnel",
                "x": 15 - 6,
                "y": 15 + 2,
                "properties": {
                    "Label": "W_000B",
                    "Direction": "EAST",
                    "Width": "4",
                    "Bitsize": "32"
                }
            },
            {
                "name": "com.ra4king.circuitsim.gui.peers.wiring.Tunnel",
                "x": 15 + 4,
                "y": 15 + 1,
                "properties": {
                    "Label": "W__OUT",
                    "Direction": "WEST",
                    "Width": "4",
                    "Bitsize": "32"
                }
            },
            {
                "name": "com.ra4king.circuitsim.gui.peers.wiring.Tunnel",
                "x": 15 - 1,
                "y": 15 - 3,
                "properties": {
                    "Label": "W_0001",
                    "Direction": "SOUTH",
                    "Width": "5",
                    "Bitsize": "1"
                }
            }
            {
                "name": "com.ra4king.circuitsim.gui.peers.wiring.Tunnel",
                "x": 15 - 1,
                "y": 15 + 4,
                "properties": {
                    "Label": "W_0002",
                    "Direction": "NORTH",
                    "Width": "5",
                    "Bitsize": "1"
                }
            }
        ],
        "wires": []
    }]

    sig = generate_genesis_signature(dummy_circuits)
    print("Add this to the JSON:")
    print(f'"revisionSignatures": [\n  "{sig}"\n]')
