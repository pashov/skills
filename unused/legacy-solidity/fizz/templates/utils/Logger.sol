// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

library Logger {
	event Log();
	function log() internal {
		emit Log();
	}

	event LogInt(int p0);
	function logInt(int p0) internal {
		emit LogInt(p0);
	}

	event LogUint(uint p0);
	function logUint(uint p0) internal {
		emit LogUint(p0);
	}

	event LogString(string p0);
	function logString(string memory p0) internal {
		emit LogString(p0);
	}

	event LogBool(bool p0);
	function logBool(bool p0) internal {
		emit LogBool(p0);
	}

	event LogAddress(address p0);
	function logAddress(address p0) internal {
		emit LogAddress(p0);
	}

	event LogBytes(bytes p0);
	function logBytes(bytes memory p0) internal {
		emit LogBytes(p0);
	}

	event LogBytes1(bytes1 p0);
	function logBytes1(bytes1 p0) internal {
		emit LogBytes1(p0);
	}

	event LogBytes2(bytes2 p0);
	function logBytes2(bytes2 p0) internal {
		emit LogBytes2(p0);
	}

	event LogBytes3(bytes3 p0);
	function logBytes3(bytes3 p0) internal {
		emit LogBytes3(p0);
	}

	event LogBytes4(bytes4 p0);
	function logBytes4(bytes4 p0) internal {
		emit LogBytes4(p0);
	}

	event LogBytes5(bytes5 p0);
	function logBytes5(bytes5 p0) internal {
		emit LogBytes5(p0);
	}

	event LogBytes6(bytes6 p0);
	function logBytes6(bytes6 p0) internal {
		emit LogBytes6(p0);
	}

	event LogBytes7(bytes7 p0);
	function logBytes7(bytes7 p0) internal {
		emit LogBytes7(p0);
	}

	event LogBytes8(bytes8 p0);
	function logBytes8(bytes8 p0) internal {
		emit LogBytes8(p0);
	}

	event LogBytes9(bytes9 p0);
	function logBytes9(bytes9 p0) internal {
		emit LogBytes9(p0);
	}

	event LogBytes10(bytes10 p0);
	function logBytes10(bytes10 p0) internal {
		emit LogBytes10(p0);
	}

	event LogBytes11(bytes11 p0);
	function logBytes11(bytes11 p0) internal {
		emit LogBytes11(p0);
	}

	event LogBytes12(bytes12 p0);
	function logBytes12(bytes12 p0) internal {
		emit LogBytes12(p0);
	}

	event LogBytes13(bytes13 p0);
	function logBytes13(bytes13 p0) internal {
		emit LogBytes13(p0);
	}

	event LogBytes14(bytes14 p0);
	function logBytes14(bytes14 p0) internal {
		emit LogBytes14(p0);
	}

	event LogBytes15(bytes15 p0);
	function logBytes15(bytes15 p0) internal {
		emit LogBytes15(p0);
	}

	event LogBytes16(bytes16 p0);
	function logBytes16(bytes16 p0) internal {
		emit LogBytes16(p0);
	}

	event LogBytes17(bytes17 p0);
	function logBytes17(bytes17 p0) internal {
		emit LogBytes17(p0);
	}

	event LogBytes18(bytes18 p0);
	function logBytes18(bytes18 p0) internal {
		emit LogBytes18(p0);
	}

	event LogBytes19(bytes19 p0);
	function logBytes19(bytes19 p0) internal {
		emit LogBytes19(p0);
	}

	event LogBytes20(bytes20 p0);
	function logBytes20(bytes20 p0) internal {
		emit LogBytes20(p0);
	}

	event LogBytes21(bytes21 p0);
	function logBytes21(bytes21 p0) internal {
		emit LogBytes21(p0);
	}

	event LogBytes22(bytes22 p0);
	function logBytes22(bytes22 p0) internal {
		emit LogBytes22(p0);
	}

	event LogBytes23(bytes23 p0);
	function logBytes23(bytes23 p0) internal {
		emit LogBytes23(p0);
	}

	event LogBytes24(bytes24 p0);
	function logBytes24(bytes24 p0) internal {
		emit LogBytes24(p0);
	}

	event LogBytes25(bytes25 p0);
	function logBytes25(bytes25 p0) internal {
		emit LogBytes25(p0);
	}

	event LogBytes26(bytes26 p0);
	function logBytes26(bytes26 p0) internal {
		emit LogBytes26(p0);
	}

	event LogBytes27(bytes27 p0);
	function logBytes27(bytes27 p0) internal {
		emit LogBytes27(p0);
	}

	event LogBytes28(bytes28 p0);
	function logBytes28(bytes28 p0) internal {
		emit LogBytes28(p0);
	}

	event LogBytes29(bytes29 p0);
	function logBytes29(bytes29 p0) internal {
		emit LogBytes29(p0);
	}

	event LogBytes30(bytes30 p0);
	function logBytes30(bytes30 p0) internal {
		emit LogBytes30(p0);
	}

	event LogBytes31(bytes31 p0);
	function logBytes31(bytes31 p0) internal {
		emit LogBytes31(p0);
	}

	event LogBytes32(bytes32 p0);
	function logBytes32(bytes32 p0) internal {
		emit LogBytes32(p0);
	}

	event Log(uint p0);
	function log(uint p0) internal {
		emit Log(p0);
	}

	event Log(string p0);
	function log(string memory p0) internal {
		emit Log(p0);
	}

	event Log(bool p0);
	function log(bool p0) internal {
		emit Log(p0);
	}

	event Log(address p0);
	function log(address p0) internal {
		emit Log(p0);
	}

	event Log(uint p0, uint p1);
	function log(uint p0, uint p1) internal {
		emit Log(p0, p1);
	}

	event Log(uint p0, string p1);
	function log(uint p0, string memory p1) internal {
		emit Log(p0, p1);
	}

	event Log(uint p0, bool p1);
	function log(uint p0, bool p1) internal {
		emit Log(p0, p1);
	}

	event Log(uint p0, address p1);
	function log(uint p0, address p1) internal {
		emit Log(p0, p1);
	}

	event Log(string p0, uint p1);
	function log(string memory p0, uint p1) internal {
		emit Log(p0, p1);
	}

	event Log(string p0, string p1);
	function log(string memory p0, string memory p1) internal {
		emit Log(p0, p1);
	}

	event Log(string p0, bool p1);
	function log(string memory p0, bool p1) internal {
		emit Log(p0, p1);
	}

	event Log(string p0, address p1);
	function log(string memory p0, address p1) internal {
		emit Log(p0, p1);
	}

	event Log(bool p0, uint p1);
	function log(bool p0, uint p1) internal {
		emit Log(p0, p1);
	}

	event Log(bool p0, string p1);
	function log(bool p0, string memory p1) internal {
		emit Log(p0, p1);
	}

	event Log(bool p0, bool p1);
	function log(bool p0, bool p1) internal {
		emit Log(p0, p1);
	}

	event Log(bool p0, address p1);
	function log(bool p0, address p1) internal {
		emit Log(p0, p1);
	}

	event Log(address p0, uint p1);
	function log(address p0, uint p1) internal {
		emit Log(p0, p1);
	}

	event Log(address p0, string p1);
	function log(address p0, string memory p1) internal {
		emit Log(p0, p1);
	}

	event Log(address p0, bool p1);
	function log(address p0, bool p1) internal {
		emit Log(p0, p1);
	}

	event Log(address p0, address p1);
	function log(address p0, address p1) internal {
		emit Log(p0, p1);
	}

	event Log(uint p0, uint p1, uint p2);
	function log(uint p0, uint p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, uint p1, string p2);
	function log(uint p0, uint p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, uint p1, bool p2);
	function log(uint p0, uint p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, uint p1, address p2);
	function log(uint p0, uint p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, string p1, uint p2);
	function log(uint p0, string memory p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, string p1, string p2);
	function log(uint p0, string memory p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, string p1, bool p2);
	function log(uint p0, string memory p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, string p1, address p2);
	function log(uint p0, string memory p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, bool p1, uint p2);
	function log(uint p0, bool p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, bool p1, string p2);
	function log(uint p0, bool p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, bool p1, bool p2);
	function log(uint p0, bool p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, bool p1, address p2);
	function log(uint p0, bool p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, address p1, uint p2);
	function log(uint p0, address p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, address p1, string p2);
	function log(uint p0, address p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, address p1, bool p2);
	function log(uint p0, address p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(uint p0, address p1, address p2);
	function log(uint p0, address p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, uint p1, uint p2);
	function log(string memory p0, uint p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, uint p1, string p2);
	function log(string memory p0, uint p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, uint p1, bool p2);
	function log(string memory p0, uint p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, uint p1, address p2);
	function log(string memory p0, uint p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, string p1, uint p2);
	function log(string memory p0, string memory p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, string p1, string p2);
	function log(string memory p0, string memory p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, string p1, bool p2);
	function log(string memory p0, string memory p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, string p1, address p2);
	function log(string memory p0, string memory p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, bool p1, uint p2);
	function log(string memory p0, bool p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, bool p1, string p2);
	function log(string memory p0, bool p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, bool p1, bool p2);
	function log(string memory p0, bool p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, bool p1, address p2);
	function log(string memory p0, bool p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, address p1, uint p2);
	function log(string memory p0, address p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, address p1, string p2);
	function log(string memory p0, address p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, address p1, bool p2);
	function log(string memory p0, address p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(string p0, address p1, address p2);
	function log(string memory p0, address p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, uint p1, uint p2);
	function log(bool p0, uint p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, uint p1, string p2);
	function log(bool p0, uint p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, uint p1, bool p2);
	function log(bool p0, uint p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, uint p1, address p2);
	function log(bool p0, uint p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, string p1, uint p2);
	function log(bool p0, string memory p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, string p1, string p2);
	function log(bool p0, string memory p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, string p1, bool p2);
	function log(bool p0, string memory p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, string p1, address p2);
	function log(bool p0, string memory p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, bool p1, uint p2);
	function log(bool p0, bool p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, bool p1, string p2);
	function log(bool p0, bool p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, bool p1, bool p2);
	function log(bool p0, bool p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, bool p1, address p2);
	function log(bool p0, bool p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, address p1, uint p2);
	function log(bool p0, address p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, address p1, string p2);
	function log(bool p0, address p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, address p1, bool p2);
	function log(bool p0, address p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(bool p0, address p1, address p2);
	function log(bool p0, address p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, uint p1, uint p2);
	function log(address p0, uint p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, uint p1, string p2);
	function log(address p0, uint p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, uint p1, bool p2);
	function log(address p0, uint p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, uint p1, address p2);
	function log(address p0, uint p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, string p1, uint p2);
	function log(address p0, string memory p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, string p1, string p2);
	function log(address p0, string memory p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, string p1, bool p2);
	function log(address p0, string memory p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, string p1, address p2);
	function log(address p0, string memory p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, bool p1, uint p2);
	function log(address p0, bool p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, bool p1, string p2);
	function log(address p0, bool p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, bool p1, bool p2);
	function log(address p0, bool p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, bool p1, address p2);
	function log(address p0, bool p1, address p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, address p1, uint p2);
	function log(address p0, address p1, uint p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, address p1, string p2);
	function log(address p0, address p1, string memory p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, address p1, bool p2);
	function log(address p0, address p1, bool p2) internal {
		emit Log(p0, p1, p2);
	}

	event Log(address p0, address p1, address p2);
	function log(address p0, address p1, address p2) internal {
		emit Log(p0, p1, p2);
	}
}
