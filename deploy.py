import os
import json
from datetime import datetime as dt
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables from .env file
load_dotenv()

# Set up Web3 provider
WEB3_PROVIDER = os.getenv("WEB3_PROVIDER")
w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))

# Define constants
CHAIN_ID = int(os.getenv("CHAIN_ID", 1))  # Default to mainnet if not specified
MANAGER_CONTRACT_ADDRESS = "0xC690ce62e557B7e7687DFb58945D49022851621A"
AGGREGATOR_CONTRACT_ADDRESS = "0x2A0B10368e69E35a330Fac7DeFcC9dC879e8B021"

# Load ABI files
with open("ABI/edl_election.json") as f:
    manager_abi = json.load(f)
with open("ABI/manage.json") as f:
    aggregator_abi = json.load(f)
with open("ABI/data.json") as f:
    aggregator_abi = json.load(f)

class WrappedElection:
    def __str__(self):
        return self.name

    def __init__(self, election_address: str, election_name: str):
        with open("abi/Election.json") as f:
            abi = json.load(f)
        self.contract = w3.eth.contract(address=election_address, abi=abi)
        self.name = election_name

class WrappedCandidate:
    def __str__(self):
        return self.name

    def __init__(self, votes: int, candidate_name: str, candidate_address: str):
        self.address = candidate_address
        self.name = candidate_name
        self.votes = votes

class ElectionData:
    def __init__(self, raw_election_data):
        self.election_name = raw_election_data[0]
        self.voters = set(raw_election_data[1])
        self.owner = raw_election_data[3]
        self.candidate_fee = raw_election_data[4]
        self.election_end_time = raw_election_data[5]
        self.election_start_time = raw_election_data[6]
        self.closed = raw_election_data[7]
        self.ranks = []

        raw_candidates = raw_election_data[2]
        wrapped_candidates = []
        candidate_addresses = []
        for raw_candidate in raw_candidates:
            wrapped_candidates.append(
                WrappedCandidate(raw_candidate[0], raw_candidate[1], raw_candidate[2])
            )
            candidate_addresses.append(raw_candidate[2])
        # Sort wrapped candidates by votes
        self.wrapped_candidates = sorted(
            wrapped_candidates,
            key=lambda wrapped_candidate: wrapped_candidate.votes,
            reverse=True,
        )
        self.candidate_addresses = set(candidate_addresses)

        # Calculate rank of each Candidate.
        # Note that if two candidates have the same amount of votes, they are the same rank.
        for i, wrapped_candidate in enumerate(wrapped_candidates):
            # If the candidate is the first in the sorted list, it is rank 1
            if i == 0:
                self.ranks.append(1)
            else:
                # If the candidate has the same amount of votes as the one before it, it is the same rank
                if wrapped_candidate.votes == wrapped_candidates[i - 1].votes:
                    self.ranks.append(self.ranks[i - 1])
                else:
                    self.ranks.append(self.ranks[i - 1] + 1)

class Account:
    def __str__(self):
        return self.address

    def __init__(self, private_key):
        self.private_key = private_key
        self.address = w3.eth.account.from_key(private_key).address

def get_elections(manager_contract, aggregator_contract):
    elections = []
    raw_election_bundles = aggregator_contract.functions.getElectionsBundledWithNames(
        manager_contract.address
    ).call()
    for raw_election_bundle in raw_election_bundles:
        elections.append(
            WrappedElection(raw_election_bundle[0], raw_election_bundle[1])
        )

    return elections

def get_balance(address):
    return w3.eth.get_balance(address)

def get_election_data(
    wrapped_election: WrappedElection, aggregator_contract
) -> ElectionData:
    return ElectionData(
        aggregator_contract.functions.getElectionData(
            wrapped_election.contract.address
        ).call()
    )

def create_election(manager_contract, election_name, election_end_time, from_account):
    if election_name is None or election_name == "":
        raise ValueError("Election name cannot be empty")

    w3.eth.wait_for_transaction_receipt(
        w3.eth.send_raw_transaction(
            w3.eth.account.sign_transaction(
                manager_contract.functions.createElection(
                    election_name, election_end_time
                ).buildTransaction(
                    {
                        "chainId": CHAIN_ID,
                        "from": from_account.address,
                        "nonce": w3.eth.get_transaction_count(from_account.address),
                        "gasPrice": w3.eth.gas_price,
                    }
                ),
                private_key=from_account.private_key,
            ).rawTransaction
        )
    )

def run_for_office(
    wrapped_election: WrappedElection, candidate_name: str, from_account: Account
):
    w3.eth.wait_for_transaction_receipt(
        w3.eth.send_raw_transaction(
            w3.eth.account.sign_transaction(
                wrapped_election.contract.functions.runForElection(
                    candidate_name
                ).buildTransaction(
                    {
                        "chainId": CHAIN_ID,
                        "from": from_account.address,
                        "nonce": w3.eth.get_transaction_count(from_account.address),
                        "gasPrice": w3.eth.gas_price,
                        "value": w3.toWei("0.05", "ether"),
                    }
                ),
                private_key=from_account.private_key,
            ).rawTransaction
        )
    )

def withdraw_revenue(wrapped_election: WrappedElection, from_account: Account):
    w3.eth.wait_for_transaction_receipt(
        w3.eth.send_raw_transaction(
            w3.eth.account.sign_transaction(
                wrapped_election.contract.functions.withdrawRevenue().buildTransaction(
                    {
                        "chainId": CHAIN_ID,
                        "from": from_account.address,
                        "nonce": w3.eth.get_transaction_count(from_account.address),
                        "gasPrice": w3.eth.gas_price,
                    }
                ),
                private_key=from_account.private_key,
            ).rawTransaction
        )
    )

def load_accounts_from_dotenv():
    accounts = []
    for private_key in get_parsed_private_keys():
        accounts.append(Account(private_key))
    return accounts

# Returns empty list if .env does not exist
def get_parsed_private_keys():
    if enumerate(".env"):
        load_dotenv()
        return os.getenv("PRIVATE_KEY", "").split(",")
    else:
        return []

def main():
    # Load accounts from .env file
    accounts = load_accounts_from_dotenv()
    if not accounts:
        print("No accounts found in .env file.")
        return

    # Load contracts
    manager_contract = w3.eth.contract(address=MANAGER_CONTRACT_ADDRESS, abi=manager_abi)
    aggregator_contract = w3.eth.contract(address=AGGREGATOR_CONTRACT_ADDRESS, abi=aggregator_abi)

    # Get all elections
    elections = get_elections(manager_contract, aggregator_contract)
    for election in elections:
        print(f"Election: {election}")

    # Get election data for the first election
    if elections:
        election_data = get_election_data(elections[0], aggregator_contract)
        print(f"Election Data: {vars(election_data)}")

    # Example usage of creating an election (uncomment if needed)
    # create_election(manager_contract, "New Election", int(dt.now().timestamp()) + 3600, accounts[0])

    # Example usage of running for office (uncomment if needed)
    # run_for_office(elections[0], "Candidate Name", accounts[0])

    # Example usage of withdrawing revenue (uncomment if needed)
    # withdraw_revenue(elections[0], accounts[0])

if __name__ == "__main__":
    main()