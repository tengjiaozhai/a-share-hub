from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user, get_current_user_id
from src.domain.interfaces.decision_run_repository import DecisionRunRepository
from src.domain.value_objects.symbol import Symbol
from src.storage.dependencies import get_decision_run_repository
from src.use_cases.create_decision_run import CreateDecisionRunRequest, CreateDecisionRunUseCase

router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


@router.get("/decision-runs")
def list_decision_runs(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: DecisionRunRepository = Depends(get_decision_run_repository),  # noqa: B008
) -> list[dict]:
    return repository.list_decision_runs(user_id=user_id)


@router.get("/decision-runs/{decision_run_id}")
def get_decision_run(
    decision_run_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: DecisionRunRepository = Depends(get_decision_run_repository),  # noqa: B008
) -> dict:
    record = repository.get_decision_run(user_id=user_id, decision_run_id=decision_run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="decision run not found")
    return record


@router.post("/decision-runs")
def create_decision_run(
    symbol: str,
    mock_llm: bool = False,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: DecisionRunRepository = Depends(get_decision_run_repository),  # noqa: B008
) -> dict:
    """创建决策运行"""
    try:
        symbol_obj = Symbol(symbol)

        use_case = CreateDecisionRunUseCase(
            decision_run_repository=repository,
        )

        request = CreateDecisionRunRequest(
            symbol=symbol_obj,
            mock_llm=mock_llm,
            user_id=user_id,
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
