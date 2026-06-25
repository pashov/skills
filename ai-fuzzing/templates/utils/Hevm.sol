// SPDX-License-Identifier: Unlicense
pragma solidity >=0.6.2 <0.9.0;

// source: https://github.com/crytic/properties/blob/main/contracts/util/IHevm.sol

interface IHevm {
    // Set block.timestamp to newTimestamp
    function warp(uint256 newTimestamp) external;

    // Set block.number to newNumber
    function roll(uint256 newNumber) external;

    // Add the condition b to the assumption base for the current branch
    // This function is almost identical to require
    function assume(bool b) external;

    // Sets the eth balance of usr to amt
    function deal(address usr, uint256 amt) external;

    // Loads a storage slot from an address
    function load(address where, bytes32 slot) external returns (bytes32);

    // Stores a value to an address' storage slot
    function store(address where, bytes32 slot, bytes32 value) external;

    // Signs data (privateKey, digest) => (v, r, s)
    function sign(
        uint256 privateKey,
        bytes32 digest
    ) external returns (uint8 v, bytes32 r, bytes32 s);

    // Gets address for a given private key
    function addr(uint256 privateKey) external returns (address addr);

    // Performs a foreign function call via terminal
    function ffi(
        string[] calldata inputs
    ) external returns (bytes memory result);

    // Performs the next smart contract call with specified msg.sender
    function prank(address newSender) external;

    // Creates a new fork with the given endpoint and the latest block and returns the identifier of the fork
    function createFork(string calldata urlOrAlias) external returns (uint256);

    // Takes a fork identifier created by createFork and sets the corresponding forked state as active
    function selectFork(uint256 forkId) external;

    // Returns the identifier of the current fork
    function activeFork() external returns (uint256);

    // Labels the address in traces
    function label(address addr, string calldata label) external;

    // Sets msg.sender to the specified sender until stopPrank() is called
    function startPrank(address sender) external;

    // Resets msg.sender to the default sender
    function stopPrank() external;
}

IHevm constant vm = IHevm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);
