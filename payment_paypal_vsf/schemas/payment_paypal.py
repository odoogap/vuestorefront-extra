# -*- coding: utf-8 -*-
# Copyright 2025 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import graphene
from graphene.types import generic
from graphql import GraphQLError

from odoo import _

from odoo.addons.payment import utils as payment_utils
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
        order = website.sale_get_order()
        domain = [
            ('id', '=', provider_id),
            ('state', 'in', ['enabled', 'test']),
        ]

        payment_provider = PaymentProvider.search(domain, limit=1)
        payment_method = payment_provider.payment_method_ids[0] if payment_provider.payment_method_ids else None

        if not payment_method:
            raise GraphQLError(_('Payment Method does not exist.'))

        if not payment_provider:
            raise GraphQLError(_('Payment Provider does not exist.'))

        if not payment_provider.code == 'paypal':
            raise GraphQLError(_('Payment Provider "Paypal" does not exist.'))

        # Generate a new access token
        access_token = payment_utils.generate_access_token(order.partner_id.id, order.amount_total, order.currency_id.id)
        order.access_token = access_token

        transaction = PaymentPortal().shop_payment_transaction(
            order_id=order.id,
            access_token=order.access_token,
            provider_id=provider_id,
            payment_method_id=payment_method.id,
            token_id=None,
            amount=order.amount_total,
            flow='redirect',
            tokenization_requested=False,
            landing_route='/shop/payment/validate',
        )

        transaction_id = PaymentTransaction.search([('reference', '=', transaction['reference'])], limit=1)

        # Update the field created_on_vsf
        transaction_id.created_on_vsf = True

        return PaypalTransactionResult(transaction=transaction)


class PaypalPaymentMutation(graphene.ObjectType):
    paypal_transaction = PaypalTransaction.Field(description='Create Paypal Transaction.')
