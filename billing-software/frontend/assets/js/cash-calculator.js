function computeCashReport(cashSales, totalExpense, openingBalance, denomTotal) {
    var cAtOffice = cashSales - totalExpense;
    var cashBalance = cAtOffice + openingBalance;
    var difference = denomTotal - cashBalance;
    return {
        cAtOffice: cAtOffice,
        cashBalance: cashBalance,
        difference: difference
    };
}
