# -*- coding: utf-8 -*-
# Copyright 2025 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
import pprint
import werkzeug

from werkzeug.exceptions import Forbidden

from odoo import http, _
from odoo.http import request
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_paypal.const import PAYMENT_STATUS_MAPPING
from odoo.addons.payment_paypal.controllers.main import PaypalController
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

_logger = logging.getLogger(__name__)


class PaypalControllerInherit(PaypalController):
    _return_url = PaypalController()._return_url
    _cancel_url = PaypalController()._cancel_url
    _webhook_url = PaypalController()._webhook_url

    @http.route(
        _return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False,
        save_session=False
    )
    def paypal_return_from_checkout(self, **pdt_data):
        """ Process the PDT notification sent by PayPal after redirection from checkout.

        The PDT (Payment Data Transfer) notification contains the parameters necessary to verify the
        origin of the notification and retrieve the actual notification data, if PDT is enabled on
        the account. See https://developer.paypal.com/api/nvp-soap/payment-data-transfer/.

        The route accepts both GET and POST requests because PayPal seems to switch between the two
        depending on whether PDT is enabled, whether the customer pays anonymously (without logging
        in on PayPal), whether they click on "Return to Merchant" after paying, etc.

        The route is flagged with `save_session=False` to prevent Odoo from assigning a new session
        to the user if they are redirected to this route with a POST request. Indeed, as the session
        cookie is created without a `SameSite` attribute, some browsers that don't implement the
        recommended default `SameSite=Lax` behavior will not include the cookie in the redirection
        request from the payment provider to Odoo. As the redirection to the '/payment/status' page
        will satisfy any specification of the `SameSite` attribute, the session of the user will be
        retrieved and with it the transaction which will be immediately post-processed.

        :param dict pdt_data: The PDT notification data send by PayPal.
        """
        _logger.info("Handling redirection from PayPal with data:\n%s", pprint.pformat(pdt_data))

        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'paypal', pdt_data
        )

        # Check the Order and respective website related with the transaction
        # Check the payment_return url for the success and error pages
        # Pass the transaction_id on the session
        sale_order_ids = tx_sudo.sale_order_ids.ids
        sale_order = request.env['sale.order'].sudo().search([
            ('id', 'in', sale_order_ids), ('website_id', '!=', False)
        ], limit=1)

        # Get Website
        website = sale_order.website_id
        # Redirect to VSF
        vsf_payment_success_return_url = website.vsf_payment_success_return_url
        vsf_payment_error_return_url = website.vsf_payment_error_return_url

        request.session["__payment_monitored_tx_id__"] = tx_sudo.id

        try:
            notification_data = self._verify_pdt_notification_origin(pdt_data, tx_sudo)
        except Forbidden:
            _logger.exception("Could not verify the origin of the PDT; discarding it.")
        else:
            tx_sudo._handle_notification_data('paypal', notification_data)

        # Transaction created on VSF
        if tx_sudo and tx_sudo.created_on_vsf:
            payment_status = notification_data.get('payment_status')
            pending_reason = notification_data.get('pending_reason')
            if (
                payment_status in PAYMENT_STATUS_MAPPING['done'] or
                payment_status in PAYMENT_STATUS_MAPPING['authorized'] or
                (payment_status in PAYMENT_STATUS_MAPPING['pending'] and pending_reason == 'authorization')
            ):
                # Confirm sale order
                # PaymentPostProcessing().poll_status()
                return werkzeug.utils.redirect(vsf_payment_success_return_url)
            else:
                return werkzeug.utils.redirect(vsf_payment_error_return_url)
        # Default Condition
        else:
            # Redirect the user to the status page.
            return request.redirect('/payment/status')

    @http.route(
        _cancel_url, type='http', auth='public', methods=['GET'], csrf=False, save_session=False
    )
    def paypal_return_from_canceled_checkout(self, tx_ref, return_access_tkn):
        """ Process the transaction after the customer has canceled the payment.

        :param str tx_ref: The reference of the transaction having been canceled.
        :param str return_access_tkn: The access token to verify the authenticity of the request.
                                      PayPal forbids any parameter with the name "token" inside.
        """
        _logger.info(
            "Handling redirection from Paypal for cancellation of transaction with reference %s",
            tx_ref,
        )

        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'paypal', {'item_number': tx_ref}
        )

        # Check the Order and respective website related with the transaction
        # Check the payment_return url for the success and error pages
        # Pass the transaction_id on the session
        sale_order_ids = tx_sudo.sale_order_ids.ids
        sale_order = request.env['sale.order'].sudo().search([
            ('id', 'in', sale_order_ids), ('website_id', '!=', False)
        ], limit=1)

        # Get Website
        website = sale_order.website_id
        # Redirect to VSF
        vsf_payment_error_return_url = website.vsf_payment_error_return_url

        request.session["__payment_monitored_tx_id__"] = tx_sudo.id

        if not payment_utils.check_access_token(return_access_tkn, tx_ref):
            raise Forbidden()
        tx_sudo._handle_notification_data('paypal', {})

        # Transaction created on VSF
        if tx_sudo and tx_sudo.created_on_vsf:
            return werkzeug.utils.redirect(vsf_payment_error_return_url)
        # Default Condition
        else:
            # Redirect the user to the status page.
            return request.redirect('/payment/status')
