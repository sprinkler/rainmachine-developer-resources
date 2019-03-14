/*
 *	Copyright (c) 2015 RainMachine, Green Electronics LLC
 *	All rights reserved.
 */

//TODO parallel processing of multiple Async objects (needed in zones and charts)

function Async() {
	this.queue = [];
	this.ready = false;
	this.result = null;
	this.debug = false;
	this.onError = null;
	this.onErrorParams = null;
};

Async.prototype.start = function(callback, param) {
	if (callback) {
		callback.call(this, param);
	}

	return this;
};

Async.prototype.then = function(callback) {
	if (typeof callback === "function") {
        if (this.ready) {
        	this.debug && console.log("ASYNC: then() callback()");
        	callback.call(this, result);
        } else {
            this.queue.push(callback);
            this.debug && console.log("ASYNC: then() NOT ready queue(%d): %o", this.queue.length, this.queue);
        }
    }
    return this;
};

Async.prototype.resolve = function() {
    var instance = this;
    var callbackArgs = arguments;

    if (! this.ready) {
		this.ready = true;
        this.queue.forEach(function (value, index, ar) {
        	instance.debug && console.log("ASYNC: function: %o, args(%d): %o", value, callbackArgs.length, callbackArgs);
            value.apply(instance, callbackArgs);
        });

        this.queue = undefined;
    }
    else {
		console.log("ASYNC: resolve() messed up !");
    }
};

Async.prototype.reject = function(error) {
    this.debug && console.log("ASYNC: Error detected queue(%d): %o", this.queue.length, this.queue);

    if (this.onError) {
        this.onError.call(null, this.onErrorParams);
		console.log("Async Error: %s", error);
    } else {
		console.log("No error handlers");
	}

    this.ready = false;
    this.queue = undefined;
};

Async.prototype.error = function(callback, paramsArray) {
    this.onError = callback;
	this.onErrorParams = paramsArray;
};
