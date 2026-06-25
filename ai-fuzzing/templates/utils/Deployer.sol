// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

// Source: https://solidity-by-example.org/app/deploy-any-contract/

contract Deployer {
    function deploy(bytes memory _code) internal returns (address addr) {
        return deploy(_code, 0);
    }

    function deploy(bytes memory _code, uint256 _value) internal returns (address addr) {
        assembly {
            addr := create(_value, add(_code, 0x20), mload(_code))
        }
        require(addr != address(0), "Deployer.sol: deploy failed");
    }
}
