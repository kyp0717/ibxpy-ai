# Python Phase Tester Agent Implementation Guide

## How to Use This Agent

### Basic Invocation
When you need to test a specific phase of the TWS trading application:

```
Use the Task tool with subagent_type: "python-phase-tester"
```

### Example Invocations

#### Test a Single Phase
```
User: "Test Phase 6 stock quote functionality"

Assistant should invoke:
Task(
    description="Test Phase 6 quotes",
    prompt="Test Phase 6 stock quote functionality following the project plan. Read project_plan.md, check Phase 6 requirements, create and run comprehensive tests for quote retrieval and integration. Display results with color coding.",
    subagent_type="python-phase-tester"
)
```

#### Test Multiple Phases
```
User: "Run tests for Phases 7 and 8"

Assistant should invoke:
Task(
    description="Test Phases 7-8",
    prompt="Test Phases 7 and 8 following the project plan. For Phase 7, test order placement and monitoring. For Phase 8, test position tracking and closing. Run all tests in uv environment and provide detailed results.",
    subagent_type="python-phase-tester"
)
```

#### Regression Testing
```
User: "Run regression tests for all completed phases"

Assistant should invoke:
Task(
    description="Regression test all phases",
    prompt="Run regression tests for all completed phases (check tasks.md for status). Execute all existing tests in ctx-ai/tests/, verify no functionality is broken, and provide comprehensive test report.",
    subagent_type="python-phase-tester"
)
```

## Agent Task Prompts

### Phase 5 - Connection Testing
```
"Test Phase 5 TWS connection functionality. Verify connection to TWS on port 7500, test error handling, validate callbacks, and ensure reconnection logic works. Run tests in uv environment and display colored pass/fail results."
```

### Phase 6 - Quote Testing
```
"Test Phase 6 quote retrieval. Test real-time quote fetching for AAPL, validate data structure, test error cases, and run integration test with main.py. Display results in required format with test inputs/outputs."
```

### Phase 7 - Order Testing
```
"Test Phase 7 order placement. Create tests for order submission, status monitoring, partial fill handling, and user prompt interaction. Test with paper trading account and verify all order states."
```

### Phase 8 - Position Testing
```
"Test Phase 8 position monitoring. Test PnL calculations, position updates, close position logic, and order fill notifications. Verify display formats match requirements (red for loss, green for gain)."
```

### Phase 9 - Audit Testing
```
"Test Phase 9 audit functionality. Test position verification using reqPositions, commission calculations, final PnL reporting, and audit display format. Ensure all audit checks are accurate."
```

### Phase 10 - Exit Testing
```
"Test Phase 10 trade exit. Test exit workflow, state cleanup, and proper termination. Verify all resources are released and positions are properly closed."
```

### Phase 11 - CLI Testing
```
"Test Phase 11 CLI arguments. Test command-line argument parsing, error handling for missing arguments, and various input combinations. Verify application exits with error when arguments are missing."
```

## Integration with Main Assistant

### When to Invoke
The main assistant should invoke this agent when:
1. User explicitly requests testing of a phase
2. After implementing new features in a phase
3. Before marking a phase as complete
4. When debugging phase-specific issues
5. For regression testing after major changes

### Pre-Invocation Checklist
Before invoking the agent, ensure:
- [ ] TWS/IBGateway is running (for Phases 5-11)
- [ ] Virtual environment is set up
- [ ] ibapi is installed
- [ ] Project structure follows plan
- [ ] Previous phases are complete

### Post-Invocation Actions
After the agent completes:
1. Review test results
2. Fix any failures identified
3. Update tasks.md with test status
4. Commit test files to repository
5. Create phase log if all tests pass

## Error Handling

### Common Issues and Solutions

#### TWS Not Connected
```
Error: Cannot connect to TWS on port 7500
Solution: Ensure TWS is running and API connections are enabled
```

#### Missing Dependencies
```
Error: ModuleNotFoundError: ibapi
Solution: Run installation script from Phase 3
```

#### Market Closed
```
Error: No quote data available
Solution: Run during market hours or use delayed data
```

#### Test Failures
```
Error: AssertionError in test
Solution: Review implementation against requirements, fix code, rerun tests
```

## Success Metrics

A phase test session is successful when:
- ✅ All unit tests pass
- ✅ Integration tests complete without errors  
- ✅ Feature works in live TWS environment
- ✅ No regression in previous phases
- ✅ Test coverage exceeds 80%
- ✅ Performance benchmarks are met
- ✅ Logs are generated

## Advanced Usage

### Custom Test Scenarios
```
Task(
    description="Test order edge cases",
    prompt="Test Phase 7 with edge cases: invalid symbols, market/limit orders, large quantities, order cancellation, and connection drops during order placement.",
    subagent_type="python-phase-tester"
)
```

### Performance Testing
```
Task(
    description="Performance test quotes",
    prompt="Test Phase 6 performance: measure quote retrieval latency, test with multiple symbols simultaneously, verify memory usage, and benchmark against requirements.",
    subagent_type="python-phase-tester"
)
```

### Continuous Testing
```
Task(
    description="Run continuous tests",
    prompt="Set up continuous testing for Phases 5-8. Run tests every 30 minutes during market hours, log results, alert on failures, and generate daily summary.",
    subagent_type="python-phase-tester"
)
```