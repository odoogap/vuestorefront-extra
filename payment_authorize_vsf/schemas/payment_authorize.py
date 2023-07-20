# -*- coding: utf-8 -*-
# Copyright 2023 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import graphene
from graphene.types import generic
from graphql import GraphQLError
from odoo import _
from odoo.http import request

from odoo.addons.website_sale.controllers.main import PaymentPortal
from odoo.addons.payment_authorize.controllers.main import AuthorizeController
from odoo.addons.payment_authorize_vsf.controllers.main import AuthorizeControllerInherit


# ---------------------------------------- #
#           Authorize.Net Payment          #
# ---------------------------------------- #

class AuthorizeProviderInfoResult(graphene.ObjectType):
    authorize_provider_info = generic.GenericScalar()


class AuthorizeTransactionResult(graphene.ObjectType):
    transaction = generic.GenericScalar()


class AuthorizePaymentResult(graphene.ObjectType):
    authorize_payment = generic.GenericScalar()


class AuthorizeProviderInfo(graphene.Mutation):
    class Arguments:
        provider_id = graphene.Int(required=True)

    Output = AuthorizeProviderInfoResult

    @staticmethod
    def mutate(self, info, provider_id):
        env = info.context["env"]
        PaymentProvider = env['payment.provider'].sudo()
        website = env['website'].get_current_website()
        request.website = website
        domain = [
            ('id', '=', provider_id),
            ('state', 'in', ['enabled', 'test']),
        ]

        payment_provider_id = PaymentProvider.search(domain, limit=1)
        if not payment_provider_id:
            raise GraphQLError(_('Payment Provider does not exist.'))

        if not payment_provider_id.code == 'authorize':
            raise GraphQLError(_('Payment Provider "Authorize.Net" does not exist.'))

        authorize_provider_info = AuthorizeController().authorize_get_provider_info(
            provider_id=payment_provider_id.id
        )

        return AuthorizeProviderInfoResult(authorize_provider_info=authorize_provider_info)


class AuthorizeTransaction(graphene.Mutation):
    class Arguments:
        provider_id = graphene.Int(required=True)
        tokenization_requested = graphene.Boolean(default_value=False)

    Output = AuthorizeTransactionResult

    @staticmethod
    def mutate(self, info, provider_id, tokenization_requested):
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

        if not payment_provider_id.code == 'authorize':
            raise GraphQLError(_('Payment Provider "Authorize.Net" does not exist.'))

        transaction = PaymentPortal().shop_payment_transaction(
            order_id=order.id,
            access_token=order.access_token,
            payment_option_id=provider_id,
            amount=order.amount_total,
            currency_id=order.currency_id.id,
            partner_id=order.partner_id.id,
            flow='direct',
            tokenization_requested=tokenization_requested,
            landing_route='/shop/payment/validate'
        )

        transaction_id = PaymentTransaction.search([('reference', '=', transaction['reference'])], limit=1)

        # Update the field created_on_vsf
        transaction_id.created_on_vsf = True

        return AuthorizeTransactionResult(transaction=transaction)


class AuthorizePayment(graphene.Mutation):
    class Arguments:
        provider_id = graphene.Int(required=True)
        transaction_reference = graphene.String(required=True)
        access_token = graphene.String(required=True)
        opaque_data = generic.GenericScalar(required=True, description='Return response.opaqueData')

    Output = AuthorizePaymentResult

    @staticmethod
    def mutate(self, info, provider_id, transaction_reference, access_token, opaque_data):
        env = info.context["env"]
        PaymentProvider = env['payment.provider'].sudo()
        PaymentTransaction = env['payment.transaction'].sudo()
        website = env['website'].get_current_website()
        request.website = website
        domain = [
            ('id', '=', provider_id),
            ('state', 'in', ['enabled', 'test']),
        ]

        payment_provider_id = PaymentProvider.search(domain, limit=1)
        if not payment_provider_id:
            raise GraphQLError(_('Payment Provider does not exist.'))

        if not payment_provider_id.code == 'authorize':
            raise GraphQLError(_('Payment Provider "Authorize.Net" does not exist.'))

        transaction = PaymentTransaction.search([('reference', '=', transaction_reference)], limit=1)
        if not transaction:
            raise GraphQLError(_('Payment transaction does not exist.'))

        # Create Payment
        authorize_payment = AuthorizeControllerInherit().authorize_payment(
            reference=transaction.reference,
            partner_id=transaction.partner_id.id,
            access_token=access_token,
            opaque_data=opaque_data
        )

        return AuthorizePaymentResult(authorize_payment=authorize_payment)


class AuthorizePaymentMutation(graphene.ObjectType):
    authorize_provider_info = AuthorizeProviderInfo.Field(description='Get Authorize.Net Provider Info.')
    authorize_transaction = AuthorizeTransaction.Field(description='Create Authorize.Net Transaction')
    authorize_payment = AuthorizePayment.Field(description='Make Authorize.Net Payment request.')
