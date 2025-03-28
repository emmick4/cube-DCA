# cube-DCA

the main file sets up the db and cube client

then the main loop starts
    when a trade appears in the db, we spin up a corresponding worker

    when an order status from cube diverges from the db state we sync

the strategy can be pretty arbitrary, for this we have a twap and pseudocode for a liquidity maker strategy

