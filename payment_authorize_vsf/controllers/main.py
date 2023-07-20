# -*- coding: utf-8 -*-
# Copyright 2023 ERPGAP/PROMPTEQUATION LDA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
import pprint
import werkzeug

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_authorize.controllers.main import AuthorizeController
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

_logger = logging.getLogger(__name__)


class AuthorizeControllerInherit(AuthorizeController):

    @http.route('/payment/authorize/payment', type='json', auth='public')
    def authorize_payment(self, reference, partner_id, access_token, opaque_data):
        """ Make a payment request and handle the response.

        :param str reference: The reference of the transaction
        :param int partner_id: The partner making the transaction, as a `res.partner` id
        :param str access_token: The access token used to verify the provided values
        :param dict opaque_data: The payment details obfuscated by Authorize.Net
        :return: None
        """
        # Check that the transaction details have not been altered
        if not payment_utils.check_access_token(access_token, reference, partner_id):
            raise ValidationError("Authorize.Net: " + _("Received tampered payment request data."))

        # Make the payment request to Authorize.Net
        tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', reference)])
        response_content = tx_sudo._authorize_create_transaction_request(opaque_data)

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
        # vsf_payment_success_return_url = website.vsf_payment_success_return_url
        # vsf_payment_error_return_url = website.vsf_payment_error_return_url

        request.session["__payment_monitored_tx_ids__"] = [tx_sudo.id]

        # Handle the payment request response
        _logger.info(
            "payment request response for transaction with reference %s:\n%s",
            reference, pprint.pformat(response_content)
        )
        tx_sudo._handle_notification_data('authorize', {'response': response_content})

        if tx_sudo.created_on_vsf:
            status_code = response_content.get('x_response_code', '3')
            if status_code == '1':  # Approved
                status_type = response_content.get('x_type').lower()
                if status_type in ('auth_capture', 'prior_auth_capture'):
                    # Confirm sale order
                    PaymentPostProcessing().poll_status()

                    # Redirect to Success Page
                    # return werkzeug.utils.redirect(vsf_payment_success_return_url)
                    return response_content

            # Declined or Error or Held for Review
            elif status_code in ['2', '3', '4']:
                # Redirect to Error Page
                # return werkzeug.utils.redirect(vsf_payment_error_return_url)
                return response_content

            return '[accepted]'  # Acknowledge the notification
