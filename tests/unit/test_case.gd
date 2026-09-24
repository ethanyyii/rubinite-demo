class_name TestCase
extends RefCounted

var failures: Array[String] = []


func before_each() -> void:
	pass


func after_each() -> void:
	pass


func assert_true(condition: bool, msg: String = "") -> void:
	if not condition:
		failures.append("expected true. %s" % msg)


func assert_false(condition: bool, msg: String = "") -> void:
	if condition:
		failures.append("expected false. %s" % msg)


func assert_eq(actual: Variant, expected: Variant, msg: String = "") -> void:
	if actual != expected:
		failures.append("expected %s, got %s. %s" % [str(expected), str(actual), msg])


func assert_near(actual: float, expected: float, tolerance: float = 0.0001, msg: String = "") -> void:
	if absf(actual - expected) > tolerance:
		failures.append("expected %s ±%s, got %s. %s" % [expected, tolerance, actual, msg])


func assert_between(actual: float, low: float, high: float, msg: String = "") -> void:
	if actual < low or actual > high:
		failures.append("expected %s in [%s, %s]. %s" % [actual, low, high, msg])
