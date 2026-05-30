# REFINE

Currently the tool works statically, analysing the source code and make speficification in conformance with source code analysis.

The problem is that statically, REFINE cannot evaluate the behaviror of the API and can create examples that, during execution, did not works as expected.

We may allow REFINE to start the API providing the API jar file, such that, during Specification Improvement, all provided examples really works or in case it not work, the discrepancy file will indicate this possible mismatch.