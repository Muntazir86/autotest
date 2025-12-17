from autotest.pytest.plugin import SchemaHandleMark


def test_is_Autotest_test(swagger_20):
    # When a test is wrapped with `parametrize`

    @swagger_20.parametrize()
    def test():
        pass

    # Then it should be recognized as a Autotest test
    assert SchemaHandleMark.is_set(test)
