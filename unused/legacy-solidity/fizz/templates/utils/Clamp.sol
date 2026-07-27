// SPDX-License-Identifier: Unlicense
pragma solidity >=0.6.2 <0.9.0;

import {Logger} from "./Logger.sol";
import {StringUtils} from "./StringUtils.sol";

/// @author Modified from Crytic (https://github.com/crytic/properties/blob/main/contracts/util/PropertiesAsserts.sol)
contract Clamp is StringUtils {
    /// @notice Clamps value to be between low and high, both inclusive
    function clampBetween(
        uint256 value,
        uint256 low,
        uint256 high
    ) internal returns (uint256) {
        if (value < low || value > high) {
            uint256 range = high - low;
            uint256 ans = low + (value % (range + 1));
            // When range == type(uint256).max (low=0, high=max), range+1 overflows
            // to 0 causing division by zero. In that case any value is already in
            // range, so this branch is only reachable when range < type(uint256).max.
            string memory valueStr = toString(value);
            string memory ansStr = toString(ans);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                valueStr,
                " to ",
                ansStr
            );
            Logger.logString(string(message));
            return ans;
        }
        return value;
    }

    /// @notice int256 version of clampBetween
    function clampBetween(
        int256 value,
        int256 low,
        int256 high
    ) internal returns (int256) {
        if (value < low || value > high) {
            int range = high - low + 1;
            int clamped = (value - low) % (range);
            if (clamped < 0) clamped += range;
            int ans = low + clamped;
            string memory valueStr = toString(value);
            string memory ansStr = toString(ans);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                valueStr,
                " to ",
                ansStr
            );
            Logger.logString(string(message));
            return ans;
        }
        return value;
    }

    /// @notice clamps a to be less than b
    function clampLt(uint256 a, uint256 b) internal returns (uint256) {
        if (!(a < b)) {
            if(b == 0) {
                Logger.logString("clampLt cannot clamp value a to be less than zero. Check your inputs/assumptions.");
                assert(false);
            }
            uint256 value = a % b;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        }
        return a;
    }

    /// @notice int256 version of clampLt
    function clampLt(int256 a, int256 b) internal returns (int256) {
        if (!(a < b)) {
            if (b == type(int256).min) {
                Logger.logString("clampLt cannot clamp value a to be less than int256.min. Check your inputs/assumptions.");
                assert(false);
            }
            int256 value = b - 1;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        }
        return a;
    }

    /// @notice clamps a to be less than or equal to b
    function clampLte(uint256 a, uint256 b) internal returns (uint256) {
        if (!(a <= b)) {
            // When b == type(uint256).max, a <= b is always true so this
            // branch is unreachable. Safe to use b + 1 without overflow.
            uint256 value = a % (b + 1);
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        }
        return a;
    }

    /// @notice int256 version of clampLte
    function clampLte(int256 a, int256 b) internal returns (int256) {
        if (!(a <= b)) {
            int256 value = b;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        }
        return a;
    }

    /// @notice clamps a to be greater than b
    function clampGt(uint256 a, uint256 b) internal returns (uint256) {
        if (!(a > b)) {
            if (b == type(uint256).max) {
                Logger.logString("clampGt cannot clamp value a to be larger than uint256.max. Check your inputs/assumptions.");
                assert(false);
            }
            uint256 value = b + 1;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        } else {
            return a;
        }
    }

    /// @notice int256 version of clampGt
    function clampGt(int256 a, int256 b) internal returns (int256) {
        if (!(a > b)) {
            if (b == type(int256).max) {
                Logger.logString("clampGt cannot clamp value a to be larger than int256.max. Check your inputs/assumptions.");
                assert(false);
            }
            int256 value = b + 1;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        } else {
            return a;
        }
    }

    /// @notice clamps a to be greater than or equal to b
    function clampGte(uint256 a, uint256 b) internal returns (uint256) {
        if (!(a >= b)) {
            uint256 value = b;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        }
        return a;
    }

    /// @notice int256 version of clampGte
    function clampGte(int256 a, int256 b) internal returns (int256) {
        if (!(a >= b)) {
            int256 value = b;
            string memory aStr = toString(a);
            string memory valueStr = toString(value);
            bytes memory message = abi.encodePacked(
                "Clamping value ",
                aStr,
                " to ",
                valueStr
            );
            Logger.logString(string(message));
            return value;
        }
        return a;
    }
}
