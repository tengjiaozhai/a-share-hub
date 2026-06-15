from fastapi import APIRouter, Depends, HTTPException

from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.domain.value_objects.symbol import Symbol
from src.storage.dependencies import get_decision_run_repository
from src.use_cases.create_decision_run import CreateDecisionRunRequest, CreateDecisionRunUseCase

router = APIRouter(prefix="/api/v1")


@router.get("/decision-runs")
def list_decision_runs(
    repository: DecisionRunRepository = Depends(get_decision_run_repository)
) -> list[dict]:
    return repository.list_decision_runs()


@router.get("/decision-runs/{decision_run_id}")
def get_decision_run(
    decision_run_id: str,
    repository: DecisionRunRepository = Depends(get_decision_run_repository)
) -> dict:
    record = repository.get_decision_run(decision_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="decision run not found")
    return record


@router.post("/decision-runs")
def create_decision_run(
    symbol: str,
    mock_llm: bool = False,
    repository: DecisionRunRepository = Depends(get_decision_run_repository)
) -> dict:
    """创建决策运行"""
    try:
        # 验证股票代码
        symbol_obj = Symbol(symbol)

        # 创建用例
        use_case = CreateDecisionRunUseCase(
            decision_run_repository=repository,
        )

        # 执行用例
        request = CreateDecisionRunRequest(
            symbol=symbol_obj,
            mock_llm=mock_llm,
        )

        response = use_case.execute(request)

        if not response.success:
            raise HTTPException(status_code=400, detail=response.error)

        return {
            "decision_run_id": response.decision_run_id,
            "symbol": symbol,
            "status": "created",
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
