# -*- coding: utf-8 -*-
# Copyright 2023 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import graphene
from graphene.types import generic
from graphql import GraphQLError
from odoo import _
from odoo.http import request

from odoo.addons.website_sale.controllers.main import PaymentPortal


# --------------------------------- #
#           Paypal Payment          #
# --------------------------------- #

class PaypalTransactionResult(graphene.ObjectType):
    transaction = generic.GenericScalar()


class PaypalTransaction(graphene.Mutation):
    class Arguments:
        provider_id = graphene.Int(required=True)

    Output = PaypalTransactionResult

    @staticmethod
    def mutate(self, info, provider_id):
        env = info.context["env"]
        PaymentProvider = env['payment.provider'].sudo()
        PaymentTransaction = env['payment.transaction'].sudo()
        website = env['website'].get_current_website()
        request.website = website
        order = website.sale_get_order()
        domain = [
            ('id', '=', provider_id),
            ('state', 'in', ['enabled', 'test']),
        ]

        payment_provider_id = PaymentProvider.search(domain, limit=1)
        if not payment_provider_id:
            raise GraphQLError(_('Payment Provider does not exist.'))

        if not payment_provider_id.code == 'paypal':
            raise GraphQLError(_('Payment Provider "Paypal" does not exist.'))

        transaction = PaymentPortal().shop_payment_transaction(
            order_id=order.id,
            access_token=order.access_token,
            payment_option_id=provider_id,
            amount=order.amount_total,
            currency_id=order.currency_id.id,
            partner_id=order.partner_id.id,
            flow='redirect',
            tokenization_requested=False,
            landing_route='/shop/payment/validate'
        )

        transaction_id = PaymentTransaction.search([('reference', '=', transaction['reference'])], limit=1)

        # Update the field created_on_vsf
        transaction_id.created_on_vsf = True

        return PaypalTransactionResult(transaction=transaction)


class PaypalPaymentMutation(graphene.ObjectType):
    paypal_transaction = PaypalTransaction.Field(description='Create Paypal Transaction.')
