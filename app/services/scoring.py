def _validate_gln_check_digit(gln: str) -> bool:
    """GS1 standard: weighted sum mod 10 == 0."""
    if not gln.isdigit() or len(gln) != 13:
        return False
    weights = [3 if i % 2 else 1 for i in range(12)]
    total = sum(int(d) * w for d, w in zip(gln[:12], weights))
    check = (10 - (total % 10)) % 10
    return check == int(gln[12])

async def evaluate_dscsa_risk(
    payload: dict[str, Any],
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> ScoreResponse:
    score = 0
    flags: list[str] = []

    gln = _extract_gln(payload)

    # Check digit validity (20 pts)
    if _validate_gln_check_digit(gln):
        score += 20
    else:
        flags.append("GLN_CHECK_DIGIT_FAIL")

    # GLN registered in Facility table for this tenant (30 pts)
    if gln:
        result = await db.execute(
            select(Facility).where(
                Facility.gln == gln,
                Facility.tenant_id == tenant_id,
            )
        )
        if result.scalar_one_or_none():
            score += 30
        else:
            flags.append("GLN_NOT_IN_FACILITY_REGISTRY")

    # Event timestamps present and chronological (25 pts)
    event_times = _extract_event_times(payload)
    if event_times:
        score += 15
        if event_times == sorted(event_times):
            score += 10

    # EPCIS 2.0 context header present (25 pts)
    ctx = payload.get("@context","")
    if "epcis/2.0" in str(ctx).lower():
        score += 25
        flags.append("EPCIS_20_CONFIRMED") if not flags else None
    else:
        flags.append("EPCIS_VERSION_MISSING_OR_1X")

    if score >= 80: risk_tier = "LOW"
    elif score >= 50: risk_tier = "MEDIUM"
    else: risk_tier = "HIGH"

    return ScoreResponse(score=score, risk_tier=risk_tier, flags=flags)