from web3 import Web3
from eth_account.messages import encode_defunct
from app.core.config import settings
import json

class Web3Client:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
        self.chain_id = settings.POLYGON_CHAIN_ID
        self.contract_address = settings.CONTRACT_ADDRESS
        
    def verify_signature(self, message: str, signature: str, address: str) -> bool:
        """Verify that a message was signed by the given address."""
        try:
            message_hash = encode_defunct(text=message)
            signer = self.w3.eth.account.recover_message(message_hash, signature=signature)
            return signer.lower() == address.lower()
        except Exception:
            return False
    
    def hash_content(self, content: str) -> str:
        """Create a hash of the content to store on blockchain."""
        return self.w3.keccak(text=content).hex()
    
    async def anchor_hash(self, content_hash: str, owner_address: str) -> str:
        """Store a content hash on the blockchain."""
        # This would interact with a smart contract
        # For MVP, we'll just return the hash
        return content_hash
    
    async def verify_hash(self, content_hash: str) -> bool:
        """Verify a content hash exists on the blockchain."""
        # This would check the smart contract
        # For MVP, we'll just return True
        return True
    
    async def create_access_rule(self, asset_id: int, beneficiary: str, conditions: dict) -> str:
        """Create a smart contract for access rules."""
        # This would deploy a new smart contract
        # For MVP, we'll just return a mock contract ID
        return f"contract_{asset_id}_{beneficiary}"
    
    async def verify_access(self, contract_id: str, requester: str) -> bool:
        """Verify if a requester has access according to the smart contract."""
        # This would check the smart contract conditions
        # For MVP, we'll just return True
        return True

web3_client = Web3Client() 