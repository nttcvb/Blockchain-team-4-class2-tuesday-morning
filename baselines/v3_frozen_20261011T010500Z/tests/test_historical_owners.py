from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from luna_sim.config import ScenarioConfig
from luna_sim.engine import context, initialize, observation, decisions, invariants


def test_seed_wallets_resume_endogenous_decisions_outside_supplied_day():
    ctx=context(ScenarioConfig(stochastic=False))
    ctx['p']=replace(ctx['p'],hazard_base=12.)
    indices=np.concatenate(ctx['seed_indices'])
    assert len(indices)==2
    day=[t for t in ctx['index'] if pd.Timestamp('2022-05-07T00:00:00Z')<t<pd.Timestamp('2022-05-08T00:00:00Z') and t not in ctx['shocks'].index]
    for time,suppressed in [(day[0],True),(pd.Timestamp('2022-05-09T12:00:00Z'),False)]:
        book=initialize(ctx)
        book['step']=ctx['index'].get_loc(time)-1
        book=observation(ctx,book)
        out=decisions(ctx,book)
        if suppressed:
            np.testing.assert_array_equal(out['queue'][indices],0.)
        else:
            assert (out['queue'][indices]>.99*book['deposit'][indices]).all()


@pytest.mark.parametrize('owner,compensating,asset',[
    ('outside_luna','market_luna','luna_supply'),
    ('fee_luna','market_luna','luna_supply'),
    ('market_luna','outside_luna','luna_supply'),
    ('external_ust','market_ust','ust_supply'),
])
def test_total_conservation_cannot_hide_a_negative_owner(owner,compensating,asset):
    ctx=context(ScenarioConfig(stochastic=False))
    book=initialize(ctx)
    transfer=book[owner]+1.
    book[owner]-=transfer
    book[compensating]+=transfer
    with pytest.raises(AssertionError,match=f'Negative {owner}'):
        invariants(ctx,book)


def test_initial_luna_inventory_cannot_exceed_observed_supply():
    ctx=context(ScenarioConfig(stochastic=False))
    ctx['p']=replace(ctx['p'],market_luna_inventory=ctx['facts']['luna_supply']+1.)
    with pytest.raises(ValueError,match='Initial market LUNA'):
        initialize(ctx)
