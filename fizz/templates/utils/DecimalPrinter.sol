// SPDX-License-Identifier: UNLICENSED
pragma solidity >=0.6.2 <0.9.0;

library DecimalPrinter {
    function toDec(uint256 _value) public pure returns (string memory) {
        return toDec(_value, 18);
    }

    function toDec(int256 _value) public pure returns (string memory) {
        return toDec(_value, 18);
    }

    function toDec(uint256 _value, uint256 decimals) public pure returns (string memory) {
        uint256 base = 10**decimals;
        uint256 integerPart = _value / base;
        uint256 fractionalPart = _value % base;

        string memory integerPartStr = uintToStr(integerPart);
        string memory fractionalPartStr = uintToStr(fractionalPart);

        // Pad fractional part with leading zeros if necessary
        uint256 numZeros = decimals - bytes(fractionalPartStr).length;
        for (uint256 i = 0; i < numZeros; i++) {
            fractionalPartStr = string(abi.encodePacked("0", fractionalPartStr));
        }

        string memory result = string(abi.encodePacked(integerPartStr, ".", fractionalPartStr));

        return result;
    }

    function toDec(int256 _value, uint256 decimals) public pure returns (string memory) {
        if (_value < 0) {
            return string(abi.encodePacked("-", toDec(uint256(-_value), decimals)));
        } else {
            return toDec(uint256(_value), decimals);
        }
    }

    function uintToStr(uint256 _value) private pure returns (string memory) {
        if (_value == 0) {
            return "0";
        }

        uint256 temp = _value;
        uint256 digits;

        while (temp != 0) {
            digits++;
            temp /= 10;
        }

        bytes memory buffer = new bytes(digits);

        while (_value != 0) {
            digits--;
            buffer[digits] = bytes1(uint8(48 + _value % 10));
            _value /= 10;
        }

        return string(buffer);
    }
}
