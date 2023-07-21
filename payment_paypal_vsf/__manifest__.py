# -*- coding: utf-8 -*-
# Copyright 2023 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    # Application Information
    'name': 'PayPal Payment Provider to VSF',
    'category': 'Accounting/Payment Acquirers',
    'version': '16.0.1.0.0',
    'summary': 'Paypal Payment Acquirer: Adapting PayPal to VSF',

    # Author
    'author': "ERPGap",
    'website': "https://www.erpgap.com/",
    'maintainer': 'ERPGap',
    'license': 'LGPL-3',

    # Dependencies
    'depends': [
        'payment',
        'payment_paypal',
        'website_payment_paypal',
    ],

    # Views
    'data': [],

    # Technical
    'installable': True,
    'application': False,
    'auto_install': False,
}
