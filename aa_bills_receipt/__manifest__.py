# -*- coding: utf-8 -*-
{
    'name': 'Bills Receipt Creation',
    'version': '20.0.1.0.0',
    'summary': 'Create the warehouse receipt of a vendor bill in one click.',
    'description': """
Bills Receipt Creation
======================
* "Create Receipt" button on posted vendor bills: creates and confirms the incoming picking
  with the storable / consumable lines of the bill.
* Receipts smart button on the bill, linked to the receipts through a real relation
  (safe in multi-company databases).
* Receipt valued at the billed cost. Odoo 20 values the receipt on its own, straight from the
  stock move, through the locations' valuation accounts, so this module does not touch the
  bill line's account.
* Protection against duplicate receipts.
    """,
    'author': 'Allam Bushra',
    'website': 'https://www.linkedin.com/in/lomixyz/',
    'category': 'Accounting',
    'depends': ['account', 'stock', 'stock_account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
