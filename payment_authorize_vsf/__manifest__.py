# -*- coding: utf-8 -*-
# Copyright 2023 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    # Application Information
    'name': 'Authorize.Net Payment Provider to VSF',
    'category': 'Accounting/Payment Acquirers',
    'version': '16.0.1.0.0',
    'summary': 'Authorize.Net Payment Acquirer: Adapting Authorize.Net to VSF',

    # Author
    'author': "ERPGap",
    'website': "https://www.erpgap.com/",
    'maintainer': 'ERPGap',
    'license': 'LGPL-3',

    # Dependencies
    'depends': [
        'payment',
        'payment_authorize',
        'website_payment_authorize',
    ],

    # Views
    'data': [],

    # Technical
    'installable': True,
    'application': False,
    'auto_install': False,
}
